"""Action card processing with template matching and per-card ROI extraction."""

import re
import json
import os
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

import cv2
import numpy as np

from .template_matcher import TemplateMatcher, MatchResult
from ..processing.ocr_processor import OCRProcessor
from ..utils.debug_utils import DebugUtils

logger = logging.getLogger(__name__)

# Fix unicode arrows/dashes that OCR sometimes produces
ARROW_FIX = str.maketrans({"→": ">", "—": "-", "–": "-", "−": "-", "»": ">"})

# Action card OCR whitelist
ACTION_CARD_WHITELIST = "BlueRed0123456789LHR:-> "

# Regex patterns for extracting card data
FROM_TO_RE = re.compile(r"([A-Za-z]+\d?)\s*[-=]>\s*([A-Za-z]+\d?)", re.IGNORECASE)  # Blue->Red1
L_RE = re.compile(r"L\s*:?\s*(-?\d+)", re.IGNORECASE)  # Light units
H_RE = re.compile(r"H\s*:?\s*(-?\d+)", re.IGNORECASE)  # Heavy units
R_RE = re.compile(r"R\s*:?\s*(-?\d+)", re.IGNORECASE)  # Ranged units


@dataclass
class ActionCard:
    """Parsed action card data with all extracted information."""

    from_faction: str
    to_faction: str
    light_count: int
    heavy_count: int
    ranged_count: int
    is_locked: bool
    raw_text: str
    confidence: float
    x: int
    y: int
    width: int
    height: int
    template_name: str = ""


class ActionCardProcessor:
    """Action card processing with template matching and ROI-based OCR."""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or "config"
        self.template_matcher = TemplateMatcher()
        self.ocr_processor = OCRProcessor()
        self.debug_utils = DebugUtils()

        from ..processing import ROIManager

        self.roi_manager = ROIManager(os.path.join(config_path or "config", "rois.json"))

        self.locked_card_rois = {}
        self.unlocked_card_rois = {}

        self._load_card_rois()

        logger.info("ActionCardProcessor initialized")

    def process_action_cards(self, screen_image: np.ndarray) -> Dict[str, List[ActionCard]]:
        """Find and parse all action cards from screen image."""
        try:
            template_dir = os.path.join(self.config_path, "templates")
            template_paths = [
                os.path.join(template_dir, "action_card_locked.png"),
                os.path.join(template_dir, "action_card_unlocked.png"),
            ]
            mask_path = os.path.join(template_dir, "action_mask.png")

            phase_headers = self._detect_phase_headers(screen_image)

            search_area, offset_x, offset_y = self._setup_action_panel_search(screen_image)
            matches = self.template_matcher.find_matches(search_area, template_paths, mask_path)

            for match in matches:
                match.x += offset_x
                match.y += offset_y

            logger.info(f"Template matching found {len(matches)} action card candidates")

            action_cards = []
            for i, match in enumerate(matches):
                card = self._parse_single_card(screen_image, match)
                if card:
                    action_cards.append(card)
                    logger.debug(f"Successfully parsed card {i+1}/{len(matches)}")
                else:
                    logger.warning(f"Failed to parse card {i+1}/{len(matches)}")

            phase_groups = self._assign_cards_to_phases(action_cards, phase_headers)

            total_cards = sum(len(cards) for cards in phase_groups.values())
            logger.info(f"Successfully processed {total_cards} action cards across phases")

            return phase_groups

        except Exception as e:
            logger.error(f"Action card processing failed: {e}")
            return {"1": [], "2": [], "3": []}

    def extract_card_data(self, card_img: np.ndarray, is_locked: bool) -> Optional[Dict]:
        """Extract card data using ROI-based OCR."""
        try:
            card_rois = self.locked_card_rois if is_locked else self.unlocked_card_rois

            logger.debug(
                f"Processing card {card_img.shape[:2][::-1]} using {'locked' if is_locked else 'unlocked'} ROIs"
            )

            from_text, _ = self._extract_ocr_text(card_img, "from_base", card_rois["from_base"], "BlueRed123 ")
            to_text, _ = self._extract_ocr_text(card_img, "to_base", card_rois["to_base"], "BlueRed123 ")

            light_text, _ = self._extract_ocr_text(card_img, "light", card_rois["light_num"], "0123456789")
            heavy_text, _ = self._extract_ocr_text(card_img, "heavy", card_rois["heavy_num"], "0123456789")
            ranged_text, _ = self._extract_ocr_text(card_img, "ranged", card_rois["ranged_num"], "0123456789")

            lock_roi = self._crop_relative_roi(card_img, card_rois["lock"])
            detected_lock_status = self._detect_lock_status(lock_roi)

            from_faction = self._normalize_faction_name(from_text)
            to_faction = self._normalize_faction_name(to_text)
            valid_bases = ["Blue", "Red1", "Red2", "Red3"]

            if from_faction not in valid_bases or to_faction not in valid_bases:
                logger.warning(
                    f"Invalid bases: '{from_text}' -> '{to_text}' (normalized: {from_faction} -> {to_faction})"
                )
                return None

            light = int(light_text) if light_text.isdigit() else 0
            heavy = int(heavy_text) if heavy_text.isdigit() else 0
            ranged = int(ranged_text) if ranged_text.isdigit() else 0

            result = {
                "from": from_faction,
                "to": to_faction,
                "L": light,
                "H": heavy,
                "R": ranged,
                "locked": detected_lock_status,
                "raw_from": from_text,
                "raw_to": to_text,
                "raw_counts": f"L{light_text} H{heavy_text} R{ranged_text}",
            }

            logger.info(
                f"Parsed card: {from_faction} -> {to_faction} (L{light} H{heavy} R{ranged}) {'LOCKED' if detected_lock_status else 'UNLOCKED'}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to extract card data: {e}")
            return None

    def _load_card_rois(self) -> None:

        def _load_roi_file(filename: str, target_dict: dict, roi_type: str) -> bool:
            path = os.path.join(self.config_path, "rois", filename)
            if not os.path.exists(path):
                return False

            try:
                with open(path, "r") as f:
                    all_rois = json.load(f)
                for name, coords in all_rois.items():
                    if name.startswith("card_"):
                        clean_name = name.replace("card_", "")
                        target_dict[clean_name] = coords
                logger.info(f"Loaded {len(target_dict)} {roi_type} card ROIs")
                return True
            except Exception as e:
                logger.error(f"Failed to load {roi_type} card ROIs: {e}")
                return False

        locked_loaded = _load_roi_file("locked_card_rois.json", self.locked_card_rois, "locked")
        unlocked_loaded = _load_roi_file("unlocked_card_rois.json", self.unlocked_card_rois, "unlocked")

        if not locked_loaded and not unlocked_loaded:
            logger.warning("No card ROI files found, using fallback coordinates")
            fallback_rois = {
                "from_base": (0.05, 0.15, 0.35, 0.25),
                "to_base": (0.55, 0.15, 0.35, 0.25),
                "light_num": (0.12, 0.65, 0.15, 0.20),
                "heavy_num": (0.42, 0.65, 0.15, 0.20),
                "ranged_num": (0.72, 0.65, 0.15, 0.20),
                "lock": (0.83, 0.60, 0.15, 0.34),
            }
            self.locked_card_rois = fallback_rois.copy()
            self.unlocked_card_rois = fallback_rois.copy()

    def _parse_single_card(self, screen_image: np.ndarray, match: MatchResult) -> Optional[ActionCard]:
        try:
            x, y, w, h = match.x, match.y, match.width, match.height
            card_crop = screen_image[y : y + h, x : x + w].copy()

            self.debug_utils.save_debug_image(card_crop, f"action_card_{x}_{y}.png")

            card_data = self.extract_card_data(card_crop, match.is_locked)
            if not card_data:
                return None

            # Create ActionCard object
            action_card = ActionCard(
                from_faction=card_data["from"],
                to_faction=card_data["to"],
                light_count=card_data["L"],
                heavy_count=card_data["H"],
                ranged_count=card_data["R"],
                is_locked=card_data["locked"],
                raw_text=f"{card_data['raw_from']} -> {card_data['raw_to']} | {card_data['raw_counts']}",
                confidence=match.confidence,
                x=x,
                y=y,
                width=w,
                height=h,
                template_name=match.template_name,
            )

            return action_card

        except Exception as e:
            logger.error(f"Failed to parse action card: {e}")
            return None

    def _crop_relative_roi(self, card_img: np.ndarray, roi_fraction: Tuple[float, float, float, float]) -> np.ndarray:
        """Crop ROI from card using relative coordinates (0.0-1.0)."""
        height, width = card_img.shape[:2]
        x_rel, y_rel, w_rel, h_rel = roi_fraction

        # Convert relative to absolute coordinates and clamp to bounds
        x = max(0, min(int(x_rel * width), width - 1))
        y = max(0, min(int(y_rel * height), height - 1))
        w = max(1, min(int(w_rel * width), width - x))
        h = max(1, min(int(h_rel * height), height - y))

        cropped = card_img[y : y + h, x : x + w].copy()

        return cropped if cropped.size > 0 else np.zeros((10, 10, 3), dtype=np.uint8)

    def _extract_ocr_text(
        self, card_img: np.ndarray, roi_name: str, roi_coords: tuple, whitelist: str
    ) -> Tuple[str, float]:
        roi_img = self._crop_relative_roi(card_img, roi_coords)
        self.debug_utils.save_debug_image(roi_img, f"card_roi_{roi_name}_{id(card_img)}.png")
        text, conf = self.ocr_processor.extract_text(roi_img, whitelist=whitelist, psm=7)
        logger.debug(f"OCR {roi_name}: '{text}' (conf: {conf})")
        return text, conf

    def _normalize_faction_name(self, name: str) -> str:
        name = name.strip()

        corrections = {
            "Blue": "Blue",
            "Red1": "Red1",
            "Red2": "Red2",
            "Red3": "Red3",
            "Red 1": "Red1",
            "Red 2": "Red2",
            "Red 3": "Red3",
            "Redl": "Red1",
            "Red": "Red1",
            "Reda": "Red1",
            "Redi": "Red1",
            "8lue": "Blue",
            "Biue": "Blue",
            "Btue": "Blue",
            "Brue": "Blue",
            "Blus": "Blue",
            "81ue": "Blue",
            "Red8": "Red3",
            "Red38": "Red3",
            "Reds": "Red3",
        }

        if name in corrections:
            return corrections[name]

        valid_bases = ["Blue", "Red1", "Red2", "Red3"]
        best_match, best_score = "", 0

        for base in valid_bases:
            score = sum(1 for i, c in enumerate(base) if i < len(name) and c.lower() == name[i].lower())
            if abs(len(base) - len(name)) <= 1:
                score += 1

            if score > best_score:
                best_score, best_match = score, base

        if best_score >= 2:
            logger.debug(f"Fuzzy matched '{name}' -> '{best_match}' (score: {best_score})")
            return best_match

        return name

    def _detect_lock_status(self, lock_img: np.ndarray) -> bool:
        if len(lock_img.shape) != 3:
            return False

        try:
            hsv = cv2.cvtColor(lock_img, cv2.COLOR_BGR2HSV)

            red_mask = cv2.inRange(hsv, np.array([0, 120, 70]), np.array([10, 255, 255])) + cv2.inRange(
                hsv, np.array([170, 120, 70]), np.array([180, 255, 255])
            )

            red_pixels = cv2.countNonZero(red_mask)
            red_ratio = red_pixels / (lock_img.shape[0] * lock_img.shape[1])
            is_locked = red_ratio > 0.15

            logger.debug(f"Lock: {red_pixels} red pixels ({red_ratio:.3f}) -> {'LOCKED' if is_locked else 'UNLOCKED'}")
            return is_locked
        except Exception as e:
            logger.warning(f"Lock detection failed: {e}")
            return False

    def _detect_phase_headers(self, screen_image: np.ndarray) -> List[Tuple[int, int]]:
        try:
            action_panel_x_start = int(screen_image.shape[1] * 0.75)
            action_panel_crop = screen_image[:, action_panel_x_start:]

            preprocessor = self.ocr_processor.image_preprocessor.create_custom_preprocessor(scale_factor=1.5)
            processed = preprocessor.preprocess_for_ocr(action_panel_crop)
            text, _ = self.ocr_processor.extract_text(processed, "Phase:123 ", 6)

            phase_headers = []
            for match in re.finditer(r"Phase\s*:?\s*([1-3])", text, re.IGNORECASE):
                phase_num = int(match.group(1))
                estimated_y = int(screen_image.shape[0] * (0.15 + (phase_num - 1) * 0.30))
                phase_headers.append((phase_num, estimated_y))

            logger.debug(f"Detected phase headers: {phase_headers}")
            return sorted(phase_headers, key=lambda x: x[1])

        except Exception as e:
            logger.warning(f"Phase header detection failed: {e}")
            return []

    def _setup_action_panel_search(self, screen_image: np.ndarray) -> Tuple[np.ndarray, int, int]:
        try:
            rois = self.roi_manager.load_rois()
            if "action_panel" in rois:
                action_panel_roi = rois["action_panel"]
                height, width = screen_image.shape[:2]

                x = int(action_panel_roi[0] * width)
                y = int(action_panel_roi[1] * height)
                w = int(action_panel_roi[2] * width)
                h = int(action_panel_roi[3] * height)

                search_area = screen_image[y : y + h, x : x + w]
                logger.info(f"Limited search to action panel: ({x}, {y}, {w}, {h})")
                return search_area, x, y
            else:
                logger.warning("action_panel ROI not found, using full screen")
                return screen_image, 0, 0

        except Exception as e:
            logger.warning(f"Failed to setup action panel search: {e}")
            return screen_image, 0, 0

    def _assign_cards_to_phases(
        self, action_cards: List[ActionCard], phase_headers: List[Tuple[int, int]]
    ) -> Dict[str, List[ActionCard]]:
        try:
            sorted_cards = sorted(action_cards, key=lambda card: card.y)
            phase_groups = {"1": [], "2": [], "3": []}

            if not phase_headers:
                phase_groups["1"] = sorted_cards  # Default to phase 1
                return phase_groups

            # Assign cards based on Y position relative to headers
            for card in sorted_cards:
                card_y = card.y
                assigned_phase = "1"  # Default

                for i, (phase_num, header_y) in enumerate(phase_headers):
                    # If last header OR card is above next header
                    if i == len(phase_headers) - 1 or card_y < phase_headers[i + 1][1]:
                        if card_y >= header_y:
                            assigned_phase = str(phase_num)
                        break

                phase_groups[assigned_phase].append(card)

            for phase, cards in phase_groups.items():
                if cards:
                    logger.info(f"Phase {phase}: {len(cards)} cards")

            return phase_groups

        except Exception as e:
            logger.error(f"Phase assignment failed: {e}")
            return {"1": action_cards, "2": [], "3": []}
