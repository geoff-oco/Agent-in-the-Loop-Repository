"""OCR processing using Tesseract with game-specific field extraction methods."""

import os
import re
import logging
from typing import Optional, Tuple, Dict

import numpy as np
import pytesseract
from dotenv import load_dotenv

from ..models.schema import LER, Units, FactionUnits
from .image_preprocessor import ImagePreprocessor

# Load environment and configure Tesseract
load_dotenv()

# Configure Tesseract environment
tesseract_cmd = os.getenv("TESSERACT_CMD")
if tesseract_cmd and os.path.exists(tesseract_cmd):
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

tessdata_prefix = os.getenv("TESSDATA_PREFIX")
if tessdata_prefix:
    os.environ["TESSDATA_PREFIX"] = tessdata_prefix

logger = logging.getLogger(__name__)

# OCR Configuration Constants
DEFAULT_CONFIDENCE_THRESHOLD = 30.0
PHASE_WHITELIST = "0123456789Phase: /"
LER_WHITELIST = "0123456789:.BlueRedin favourLER "
ADJUSTMENT_WHITELIST = "0123456789+-"
UNITS_WHITELIST = "0123456789"


class OCRProcessor:
    """OCR processing using Tesseract with game-specific field extraction."""

    def __init__(self, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD):
        self.confidence_threshold = confidence_threshold
        self.image_preprocessor = ImagePreprocessor()

        try:
            pytesseract.get_tesseract_version()
            logger.info("Tesseract OCR engine available")
        except Exception as e:
            logger.error(f"Tesseract not available: {e}")

        logger.debug(f"OCRProcessor initialized with confidence threshold: {confidence_threshold}")

    def extract_text(self, img, whitelist=None, psm=7):
        """Perform OCR with character filtering and confidence calculation."""
        try:
            config = f"--oem 3 --psm {psm}"
            if whitelist:
                config += f" -c tessedit_char_whitelist={whitelist}"

            text = pytesseract.image_to_string(img, config=config).strip()
            data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)

            confidences = [int(conf) for conf in data["conf"] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else (50.0 if text.strip() else 0.0)

            if avg_confidence < self.confidence_threshold:
                logger.warning(f"Low OCR confidence: {avg_confidence:.1f}% < {self.confidence_threshold}%")

            return text, avg_confidence

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return "", 0.0

    def read_phase(self, img):
        """Extract game phase number from header region."""
        try:
            processed = self.image_preprocessor.preprocess_for_ocr(img)
            text, confidence = self.extract_text(processed, PHASE_WHITELIST, 7)

            phase_match = re.search(r"Phase[:\s]*(\d+)", text, re.IGNORECASE)
            if phase_match:
                phase = int(phase_match.group(1))
                if 1 <= phase <= 3:
                    return phase, confidence

            number_match = re.search(r"(\d+)", text)
            if number_match:
                phase = int(number_match.group(1))
                if 1 <= phase <= 3:
                    return phase, confidence * 0.7  # Lower confidence for fallback

            logger.warning(f"Could not extract phase from: '{text}'")
            return 0, 0.0

        except Exception as e:
            logger.error(f"Phase reading failed: {e}")
            return 0, 0.0

    def read_ler(self, img):
        """Extract Loss Exchange Ratio from LER panel."""
        try:
            processed = self.image_preprocessor.preprocess_for_ocr(img)
            text, confidence = self.extract_text(processed, LER_WHITELIST, 6)

            ler_match = re.search(r"LER\s+([\d.]+)\s*:\s*([\d.]+).*?(?:favour|favor).*?(Blue|Red)", text, re.IGNORECASE)
            if ler_match:
                blue_ratio, red_ratio = float(ler_match.group(1)), float(ler_match.group(2))
                favour_text = ler_match.group(3).capitalize()
                if blue_ratio > 0 and red_ratio > 0:
                    ler = LER(blue=blue_ratio, red=red_ratio, favour=favour_text, raw=text)
                    return ler, confidence

            ratio_match = re.search(r"([\d.]+)\s*:\s*([\d.]+)", text)
            if ratio_match:
                blue_ratio, red_ratio = float(ratio_match.group(1)), float(ratio_match.group(2))
                if blue_ratio > 0 and red_ratio > 0:
                    favour = "Blue" if blue_ratio >= red_ratio else "Red"
                    ler = LER(blue=blue_ratio, red=red_ratio, favour=favour, raw=text)
                    return ler, confidence * 0.8  # Lower confidence for fallback

            logger.warning(f"Could not extract LER from: '{text}'")
            return LER(blue=1.0, red=1.0, favour="Blue", raw=text), 0.0

        except Exception as e:
            logger.error(f"LER reading failed: {e}")
            default_ler = LER(blue=1.0, red=1.0, favour="Blue", raw="")
            return default_ler, 0.0

    def read_units_column(self, img, roi_name):
        """Read Light/Heavy/Ranged unit values from column."""
        try:
            scale_factor = self._get_base_scale_factor(roi_name)
            preprocessor = self.image_preprocessor.create_custom_preprocessor(scale_factor=scale_factor)
            processed = preprocessor.preprocess_for_ocr(img)

            config = "--psm 6 -c tessedit_char_whitelist=0123456789+-"
            text = pytesseract.image_to_string(processed, config=config).strip()
            avg_confidence = self._get_ocr_confidence(processed, config)

            lines = [line.strip() for line in text.split("\n") if line.strip()]
            numbers = [self._parse_unit_expression(line) for line in lines]

            while len(numbers) < 3:
                numbers.append(0)

            units = Units(light=numbers[0], heavy=numbers[1], ranged=numbers[2])
            return units, avg_confidence

        except Exception as e:
            logger.error(f"Units column reading failed for {roi_name}: {e}")
            return Units(light=0, heavy=0, ranged=0), 0.0

    def read_adjustment_cell(self, img, roi_name):
        """Read adjustment cell with +/-X values."""
        try:
            scale_factor = self._get_base_scale_factor(roi_name) * 1.5
            preprocessor = self.image_preprocessor.create_custom_preprocessor(scale_factor=scale_factor)
            processed = preprocessor.preprocess_for_ocr(img)

            configs = [
                f"--psm 7 -c tessedit_char_whitelist={ADJUSTMENT_WHITELIST}",
                f"--psm 8 -c tessedit_char_whitelist={ADJUSTMENT_WHITELIST}",
                f"--psm 6 -c tessedit_char_whitelist={ADJUSTMENT_WHITELIST}",
            ]

            best_text, best_confidence, best_value = "", 0.0, 0

            for config in configs:
                try:
                    text = pytesseract.image_to_string(processed, config=config).strip()
                    confidence = self._get_ocr_confidence(processed, config)
                    value = self._parse_adjustment_value(text)

                    if (text.startswith(("+", "-")) and confidence > best_confidence) or (
                        confidence > best_confidence and not best_text.startswith(("+", "-"))
                    ):
                        best_text, best_confidence, best_value = text, confidence, value
                except Exception:
                    continue

            if best_text.isdigit():
                best_confidence = min(best_confidence, 20.0)

            return best_value, best_confidence

        except Exception as e:
            logger.error(f"Adjustment cell reading failed for {roi_name}: {e}")
            return 0, 0.0

    def read_base_hybrid(
        self, blue_units_img: np.ndarray, blue_adj_cells: Dict[str, int], red_units_img: np.ndarray, base_name: str
    ):
        """Hybrid base reading: column OCR + granular adjustments."""
        try:
            blue_base_units, blue_units_conf = self.read_units_column(blue_units_img, f"{base_name}_blue_units")
            red_units, red_units_conf = self.read_units_column(red_units_img, f"{base_name}_red_units")

            blue_final = Units(
                light=max(0, blue_base_units.light + blue_adj_cells.get("light", 0)),
                heavy=max(0, blue_base_units.heavy + blue_adj_cells.get("heavy", 0)),
                ranged=max(0, blue_base_units.ranged + blue_adj_cells.get("ranged", 0)),
            )
            faction_units = FactionUnits(blue=blue_final, red=red_units)

            adj_count = len([v for v in blue_adj_cells.values() if v != 0])
            avg_confidence = (
                ((blue_units_conf + red_units_conf + 80.0) / 3)
                if adj_count > 0
                else ((blue_units_conf + red_units_conf) / 2)
            )

            return faction_units, avg_confidence

        except Exception as e:
            logger.error(f"Hybrid base reading failed for {base_name}: {e}")
            empty_units = FactionUnits(blue=Units(light=0, heavy=0, ranged=0), red=Units(light=0, heavy=0, ranged=0))
            return empty_units, 0.0

    def validate_extraction_result(self, field_name: str, confidence: float, min_confidence: float = 50.0) -> bool:
        """Validate OCR extraction based on confidence threshold."""
        is_valid = confidence >= min_confidence
        if not is_valid:
            logger.warning(f"Field '{field_name}' failed validation: confidence {confidence:.1f}% < {min_confidence}%")
        return is_valid

    def _get_base_scale_factor(self, roi_name: str) -> float:
        if "blue" in roi_name:
            return 2.5
        elif "red1" in roi_name:
            return 3.5
        elif "red2" in roi_name:
            return 4.0
        elif "red3" in roi_name:
            return 3.0
        return 3.0

    def _get_ocr_confidence(self, processed_img: np.ndarray, config: str) -> float:
        try:
            data = pytesseract.image_to_data(processed_img, config=config, output_type=pytesseract.Output.DICT)
            confidences = [c for c in data["conf"] if c > 0]
            return sum(confidences) / len(confidences) if confidences else 0.0
        except:
            return 50.0

    def _parse_unit_expression(self, text: str) -> int:
        try:
            if not text.strip():
                return 0
            text = text.strip().replace(" ", "")

            if "-" in text:
                parts = text.split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    return max(0, int(parts[0]) - int(parts[1]))

            if "+" in text:
                parts = text.split("+")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    return int(parts[0]) + int(parts[1])

            if text.isdigit():
                return int(text)
            numbers = re.findall(r"\d+", text)
            return int(numbers[0]) if numbers else 0

        except Exception:
            return 0

    def _parse_adjustment_value(self, text: str) -> int:
        try:
            text = text.strip().replace(" ", "")
            if not text:
                return 0

            if text.isdigit() and len(text) == 2 and text[0] in ["4", "1"]:
                return int(text[1:])

            if text.startswith(("+", "-")):
                return int(text)

            if "+" in text and "-" in text:
                number_part = text.replace("+", "").replace("-", "")
                if number_part.isdigit():
                    num = int(number_part)
                    plus_pos, minus_pos = text.find("+"), text.find("-")
                    if minus_pos < plus_pos and minus_pos != -1:
                        return -num
                    elif plus_pos < minus_pos and plus_pos != -1:
                        return num
                return 0

            if "+" in text:
                number = text.replace("+", "")
                return int(number) if number.isdigit() else 0
            if "-" in text:
                number = text.replace("-", "")
                return -int(number) if number.isdigit() else 0

            if text.isdigit():
                num = int(text)
                if 0 <= num <= 15:
                    logger.warning(f"Adjustment '{text}' missing sign - returning 0")
                    return 0
            return 0

        except (ValueError, IndexError):
            return 0
