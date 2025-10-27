# Game state management and business logic
import copy
import logging
import re
from typing import Dict, List, Optional

from core.models import ROIMeta
from core.roi_manager import ROIManager
from imaging.utils import ImageUtils
from .models import BaseUnits, PhaseData, UnitCounts


class GameStateManager:  # Manages game state transitions and calculations

    def __init__(
        self,
        screen_capture=None,
        ocr_processor=None,
        monitor_index=None,
        output_manager=None,
    ):
        # Base names for output structure
        self.base_names = ["blue", "red1", "red2", "red3"]

        # Dependencies for OCR reading
        self.screen_capture = screen_capture
        self.ocr_processor = ocr_processor
        self.monitor_index = monitor_index
        self.output_manager = output_manager

        # ROI storage for game state reading
        self.phase_roi: Optional[ROIMeta] = None
        self.ler_roi: Optional[ROIMeta] = None

        # State
        self.initial_ler: Optional[str] = None

    def build_state(self, ocr_results: Dict[str, str]) -> Dict[str, BaseUnits]:
        # Build base unit state from OCR results
        state = {}

        # Initialise all bases
        for base_name in self.base_names:
            state[base_name] = BaseUnits()

        # Parse OCR results and populate state (skip adjustment ROIs)
        for roi_name, text in ocr_results.items():
            # Skip adjustment ROIs
            if "_adj" in roi_name.lower():
                continue

            # Determine which base and faction this ROI belongs to
            # ROI naming convention: {Base}{Faction}{UnitType}
            # e.g., "Bblight" = Blue base, blue faction, light units
            #       "R1rlight" = Red1 base, red faction, light units

            base_name = None
            faction = None
            unit_type = None

            # Parse ROI name
            roi_lower = roi_name.lower()

            # Determine base
            if roi_lower.startswith("bb"):
                base_name = "blue"
                faction = "blue"
            elif roi_lower.startswith("br"):
                base_name = "blue"
                faction = "red"
            elif roi_lower.startswith("r1b"):
                base_name = "red1"
                faction = "blue"
            elif roi_lower.startswith("r1r"):
                base_name = "red1"
                faction = "red"
            elif roi_lower.startswith("r2b"):
                base_name = "red2"
                faction = "blue"
            elif roi_lower.startswith("r2r"):
                base_name = "red2"
                faction = "red"
            elif roi_lower.startswith("r3b"):
                base_name = "red3"
                faction = "blue"
            elif roi_lower.startswith("r3r"):
                base_name = "red3"
                faction = "red"

            # Determine unit type
            if "light" in roi_lower:
                unit_type = "L"
            elif "heavy" in roi_lower:
                unit_type = "H"
            elif "ranged" in roi_lower:
                unit_type = "R"

            # Apply parsed value
            if base_name and faction and unit_type:
                try:
                    value = int(text) if text and text != "(empty)" else 0
                    units = state[base_name].blue if faction == "blue" else state[base_name].red
                    setattr(units, unit_type, value)
                except ValueError:
                    pass  # Keep default 0

        return state

    def apply_zeroing(self, state: Dict[str, BaseUnits]) -> Dict[str, BaseUnits]:
        # Zero blue units if red units present
        zeroed_state = copy.deepcopy(state)

        for base_name, units in zeroed_state.items():
            # Check if any red units exist at this base
            has_red_units = units.red.L > 0 or units.red.H > 0 or units.red.R > 0

            # If red units exist, zero all blue units
            if has_red_units:
                units.blue.L = 0
                units.blue.H = 0
                units.blue.R = 0
                logging.info(f"Zeroing blue units at {base_name} due to red presence")

        return zeroed_state

    def parse_adjustment(self, adj_text: str) -> int:
        # Parse adjustment text preserving sign
        if not adj_text or adj_text.strip() == "":
            return 0

        adj_text = adj_text.strip()

        # Log raw OCR output for debugging
        logging.debug(f"Raw adjustment OCR: '{adj_text}'")

        try:
            # Direct conversion - trust OCR's sign detection
            value = int(adj_text)
            logging.debug(f"Parsed adjustment value: {value}")
            return value
        except ValueError:
            # Fallback: use regex to extract first number with optional sign
            match = re.search(r"[+-]?\d+", adj_text)
            if match:
                value = int(match.group())
                logging.debug(f"Regex parsed adjustment value: {value}")
                return value
            else:
                logging.warning(f"Could not parse adjustment value: '{adj_text}'")

        return 0

    def apply_adjustments(
        self, before_state: Dict[str, BaseUnits], ocr_results: Dict[str, str]
    ) -> Dict[str, BaseUnits]:
        # Apply adjustment values to create after state
        after_state = copy.deepcopy(before_state)

        # Process each adjustment ROI
        for adj_roi_name, adj_value in ocr_results.items():
            # Only process adjustment ROIs
            if "_adj" not in adj_roi_name.lower():
                continue

            # Parse the adjustment value
            adjustment = self.parse_adjustment(adj_value)
            if adjustment == 0:
                logging.debug(f"{adj_roi_name}: No adjustment (parsed as 0)")
                continue  # No adjustment

            logging.info(f"Processing adjustment {adj_roi_name}: {adjustment:+d}")

            # Determine which base and unit type this adjustment applies to
            # Remove "_adj" suffix to get base ROI name
            base_roi_name = adj_roi_name.replace("_adj", "")
            roi_lower = base_roi_name.lower()

            base_name = None
            unit_type = None

            # Determine base (only affects blue units)
            if roi_lower.startswith("bb"):
                base_name = "blue"
            elif roi_lower.startswith("r1b"):
                base_name = "red1"
            elif roi_lower.startswith("r2b"):
                base_name = "red2"
            elif roi_lower.startswith("r3b"):
                base_name = "red3"
            else:
                continue  # Not a blue unit adjustment

            # Determine unit type
            if "light" in roi_lower:
                unit_type = "L"
            elif "heavy" in roi_lower:
                unit_type = "H"
            elif "ranged" in roi_lower:
                unit_type = "R"

            # Apply adjustment to blue units
            if base_name and unit_type:
                current_value = getattr(after_state[base_name].blue, unit_type)
                new_value = max(0, current_value + adjustment)  # Can't go negative
                setattr(after_state[base_name].blue, unit_type, new_value)

                logging.info(
                    f"Applied adjustment to {base_name} blue {unit_type}: "
                    f"{current_value} + ({adjustment}) = {new_value}"
                )

        return after_state

    def calculate_phase_data(self, phase_num: int, ocr_results: Dict[str, str], mode: str = "full") -> PhaseData:
        # Calculate before/after states for a phase
        # mode: "full" = before + after states, "before_only" = before state only (after = None)
        # ocr_results: flat dict {roi_name: text_value} (same format as old code)
        phase_data = PhaseData(phase_number=phase_num)

        # Build base state from all OCR results (both base and adjustment ROIs are in flat dict)
        base_state = self.build_state(ocr_results)

        # Apply zeroing logic for before state
        phase_data.before = self.apply_zeroing(base_state)

        # Only calculate after state if mode is "full"
        if mode == "full":
            # Apply adjustments to get after state (adjustments are in same flat dict)
            phase_data.after = self.apply_adjustments(phase_data.before, ocr_results)
        else:
            # before_only mode - no after state (battle results only)
            phase_data.after = None

        return phase_data

    def calculate_ler(self, ler_text: str) -> Dict:
        # Parse LER text into structured format
        # Parse "LER 1.24:1 in favour of Blue"
        ler_data = {"blue": 1.0, "red": 1.0, "favour": "Neutral"}

        if not ler_text:
            return ler_data

        # Debug logging to see actual OCR text
        logging.info(f"Parsing LER text: '{ler_text}'")

        try:
            # Extract ratio
            if ":" in ler_text:
                parts = ler_text.split(":")
                if len(parts) >= 2:
                    # Extract numbers
                    blue_part = parts[0].strip()
                    for word in blue_part.split():
                        try:
                            ler_data["blue"] = float(word)
                            break
                        except ValueError:
                            continue

            # Extract favour - support both British and American spelling
            text_lower = ler_text.lower()
            if "favour of" in text_lower or "favor of" in text_lower:
                if "blue" in text_lower:
                    ler_data["favour"] = "Blue"
                    logging.info(f"LER favour detected: Blue")
                elif "red" in text_lower:
                    ler_data["favour"] = "Red"
                    logging.info(f"LER favour detected: Red")
                else:
                    logging.warning(f"LER contains 'favour/favor of' but no team name found in: '{ler_text}'")

        except Exception as e:
            logging.error(f"Error parsing LER: {e}")

        logging.info(f"Parsed LER: {ler_data}")
        return ler_data

    def get_final_state(self, phases: List[PhaseData], red2_final_count: Optional[str] = None) -> Dict[str, BaseUnits]:
        # Calculate final state after all phases
        if not phases:
            return {}

        # Last phase's after state is the final state (or before if after is None)
        last_phase = phases[-1]

        # Use after state if available, otherwise use before state
        source_state = last_phase.after if last_phase.after is not None else last_phase.before

        # Apply final battle logic if needed
        final = {}
        for base_name, units in source_state.items():
            final[base_name] = BaseUnits()

            # Copy existing unit data
            final[base_name].blue.L = units.blue.L
            final[base_name].blue.H = units.blue.H
            final[base_name].blue.R = units.blue.R
            final[base_name].red.L = units.red.L
            final[base_name].red.H = units.red.H
            final[base_name].red.R = units.red.R

            # Replace Red2 red heavy units with captured final count if available
            if base_name == "red2" and red2_final_count is not None:
                try:
                    final_count = int(red2_final_count)
                    final[base_name].red.H = final_count
                    print(f"Updated Red2 final red heavy units to: {final_count}")
                except ValueError:
                    print(f"Warning: Could not parse Red2 final count '{red2_final_count}', using calculated value")

        # Apply zeroing logic to final state (if red units present, zero blue units)
        final = self.apply_zeroing(final)

        return final

    def load_rois(self, element_roi_path: str = None) -> bool:
        # Load Phase and LER ROIs from Element ROI file
        try:
            # Use default path if not provided
            if element_roi_path is None:
                element_roi_path = "rois/rois_main/Element_rois_custom.json"

            # Load element ROIs (contains LER, Phase, buttons)
            element_manager = ROIManager()
            success, message, count = element_manager.load_from_file(element_roi_path)
            if not success:
                print(f"Failed to load element ROIs: {message}")
                return False

            # Find Phase and LER ROIs
            for name, roi in element_manager.rois.items():
                if name == "Phase":
                    self.phase_roi = roi
                    print("Found Phase ROI in Element ROIs")
                elif name == "LER":
                    self.ler_roi = roi
                    print("Found LER ROI in Element ROIs")

            return self.phase_roi is not None and self.ler_roi is not None

        except Exception as e:
            print(f"Failed to load ROIs: {e}")
            return False

    def read_ler(self) -> Optional[str]:
        # Read LER once at start of session
        if self.initial_ler is not None:
            return self.initial_ler

        if not self.ler_roi or not self.screen_capture or not self.ocr_processor:
            print("LER ROI not loaded or missing dependencies")
            return None

        try:
            # Capture screen and crop LER ROI
            frame = self.screen_capture.capture_monitor(self.monitor_index)
            if frame is None:
                print("Failed to capture screen for LER")
                return None

            roi_image = ImageUtils.crop_roi(frame, self.ler_roi)

            # Save LER capture to setup folder
            if self.output_manager:
                self.output_manager.save_capture(roi_image, phase_num="setup", roi_name="LER_Panel")

            # Process OCR using multi-engine method (tries multiple engines for better accuracy)
            accepted_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-:. "
            results = self.ocr_processor.process_multi_engine(
                roi_image,
                self.ler_roi,
                accepted_chars=accepted_chars,
                early_exit_enabled=True,
            )

            # Extract best result
            if results:
                best_result = results[0]  # Results are sorted by score
                _, _, text, confidence, rule_passed, _ = best_result
                ocr_result = type("OCRResult", (), {"text": text, "confidence": confidence})()
            else:
                ocr_result = type("OCRResult", (), {"text": "", "confidence": 0})()

            if ocr_result.text and ocr_result.confidence > 60:
                self.initial_ler = ocr_result.text.strip()
                print(f"Initial LER: '{self.initial_ler}' (confidence: {ocr_result.confidence:.1f}%)")
                return self.initial_ler

            print(f"Low confidence LER reading: {ocr_result.confidence:.1f}%")
            return None

        except Exception as e:
            print(f"Error reading LER: {e}")
            return None

    def read_phase_header(self) -> Optional[str]:
        # Read the phase header text
        if not self.phase_roi or not self.screen_capture or not self.ocr_processor:
            print("Phase ROI not loaded or missing dependencies")
            return None

        try:
            frame = self.screen_capture.capture_monitor(self.monitor_index)
            if frame is None:
                return None

            roi_image = ImageUtils.crop_roi(frame, self.phase_roi)

            # Save phase header capture to setup folder
            if self.output_manager:
                self.output_manager.save_capture(roi_image, phase_num="setup", roi_name="Phase_Header")

            # Process OCR using single-engine method (PaddleOCR GPU for speed)
            accepted_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-:. "
            results = self.ocr_processor.process_single_engine(
                roi_image,
                self.phase_roi,
                "paddle_gpu",
                accepted_chars=accepted_chars,
                early_exit_enabled=True,
            )

            # Extract best result
            if results:
                best_result = results[0]  # Results are sorted by score
                _, _, text, confidence, rule_passed, _ = best_result
                ocr_result = type("OCRResult", (), {"text": text, "confidence": confidence})()
            else:
                ocr_result = type("OCRResult", (), {"text": "", "confidence": 0})()

            if ocr_result.text:
                print(f"Phase header: '{ocr_result.text}' (confidence: {ocr_result.confidence:.1f}%)")
                return ocr_result.text

            return None

        except Exception as e:
            print(f"Error reading phase header: {e}")
            return None
