"""Main screen reading system."""

import os
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from ..capture import ScreenCapture, WindowDetector
from ..processing import ROIManager, OCRProcessor, ImagePreprocessor
from ..template_matching import ActionCardProcessor
from ..utils import DebugUtils, FileUtils
from ..models import GameState
from .game_state_builder import GameStateBuilder

logger = logging.getLogger(__name__)


class ROIResult:
    """ROI extraction result."""

    def __init__(
        self, roi_name, roi_coordinates, extracted_data, confidence, success, error_message=None, raw_text=None
    ):
        self.roi_name = roi_name
        self.roi_coordinates = roi_coordinates
        self.extracted_data = extracted_data
        self.confidence = confidence
        self.success = success
        self.error_message = error_message
        self.raw_text = raw_text


class ScreenReadingResult:
    """Complete screen reading result."""

    def __init__(self, timestamp, window_bounds, rois_processed, results, game_state=None, overall_success=False):
        self.timestamp = timestamp
        self.window_bounds = window_bounds
        self.rois_processed = rois_processed
        self.results = results
        self.game_state = game_state
        self.overall_success = overall_success

    def success_rate(self):
        if not self.results:
            return 0.0
        successful = sum(1 for result in self.results.values() if result.success)
        return successful / len(self.results)


class ScreenReadingOrchestrator:
    """Main screen reading system."""

    def __init__(self, debug: bool = False, config_path: str = "config"):
        self.debug = debug
        self.config_path = config_path

        self.screen_capture = ScreenCapture()
        self.roi_manager = ROIManager(os.path.join(config_path, "rois.json"))
        self.ocr_processor = OCRProcessor()
        self.action_card_processor = ActionCardProcessor(config_path)
        self.game_state_builder = GameStateBuilder()
        self.debug_utils = DebugUtils()

        if debug:
            logging.getLogger().setLevel(logging.DEBUG)

        logger.info("Screen reading system ready")

    def capture_and_analyze_all(self) -> ScreenReadingResult:
        """Capture screen and analyze all components."""
        start_time = time.time()
        timestamp = datetime.now()

        try:
            logger.info("Starting screen reading analysis")

            # Clean up old debug files
            self._cleanup_debug_files()

            # Step 1: Capture screen
            window_bounds, screen_image = self._capture_game_screen()
            if screen_image is None:
                return self._create_failed_result(timestamp, "Failed to capture game screen")

            logger.info(f"Captured screen image: {screen_image.shape[1]}x{screen_image.shape[0]}")
            self.debug_utils.save_debug_image(screen_image, "fullscreen.png")

            # Step 2: Load ROI definitions
            rois = self.roi_manager.load_rois()
            logger.info(f"Loaded {len(rois)} ROI definitions")

            # Step 3: Process standard ROIs
            roi_results = self._process_standard_rois(screen_image, rois)

            # Step 4: Process action cards
            action_card_results = self._process_action_cards(screen_image)
            roi_results.update(action_card_results)

            # Step 5: Build final game state
            game_state = self.game_state_builder.build_game_state(roi_results)

            # Step 6: Calculate success metrics
            successful_extractions = sum(1 for r in roi_results.values() if r.success)
            overall_success = successful_extractions > 0 and game_state is not None

            result = ScreenReadingResult(
                timestamp=timestamp,
                window_bounds=window_bounds or (),
                rois_processed=len(rois),
                results=roi_results,
                game_state=game_state,
                overall_success=overall_success,
            )

            # Log completion time
            self.debug_utils.log_processing_time("Screen reading analysis", start_time)
            logger.info(f"Analysis done: {successful_extractions}/{len(roi_results)} ROIs successful")

            return result

        except Exception as e:
            logger.error(f"Screen reading failed: {e}")
            return self._create_failed_result(timestamp, str(e))

    def process_single_roi(self, screen_image, roi_name: str, roi_coords) -> ROIResult:
        """Process a single ROI region."""
        try:
            logger.debug(f"Processing ROI: {roi_name}")

            # Crop ROI region
            roi_image = self.roi_manager.crop_roi_relative(screen_image, roi_coords)

            # Save debug image
            self.debug_utils.save_debug_image(roi_image, f"roi_{roi_name}.png", roi_name)

            # Convert relative to absolute coordinates for result
            abs_coords = self.roi_manager.convert_rois_to_absolute({roi_name: roi_coords}, screen_image.shape[:2])
            roi_abs_coords = abs_coords[roi_name]

            # Route to appropriate processing method
            if roi_name == "phase_header":
                return self._process_phase_header(roi_name, roi_image, roi_abs_coords)
            elif roi_name == "ler_panel":
                return self._process_ler_panel(roi_name, roi_image, roi_abs_coords)
            elif roi_name.endswith("_units"):
                # Store raw crop for later hybrid processing
                return self._create_roi_result(
                    roi_name, roi_abs_coords, {"raw_crop": roi_image}, 100.0, True, None, "Units column data"
                )
            elif roi_name.endswith("_adj"):
                return self._process_adjustment_cell(roi_name, roi_image, roi_abs_coords)
            else:
                return self._create_roi_result(roi_name, roi_abs_coords, error_message=f"Unknown ROI type: {roi_name}")

        except Exception as e:
            logger.error(f"Failed to process ROI {roi_name}: {e}")
            return self._create_roi_result(roi_name, roi_coords, error_message=str(e))

    def save_results(self, result: ScreenReadingResult) -> None:
        """Save processing results to files."""
        try:
            # Save simplified game state
            if result.game_state:
                simplified_data = {
                    "timestamp": result.timestamp.isoformat(),
                    "phase": result.game_state.phase,
                    "ler": {
                        "blue": result.game_state.ler.blue,
                        "red": result.game_state.ler.red,
                        "favour": result.game_state.ler.favour,
                    },
                    "bases": {
                        name: {
                            "blue": {"light": fu.blue.light, "heavy": fu.blue.heavy, "ranged": fu.blue.ranged},
                            "red": {"light": fu.red.light, "heavy": fu.red.heavy, "ranged": fu.red.ranged},
                        }
                        for name, fu in result.game_state.bases.items()
                    },
                }

                # Add actions if available
                if result.game_state.actions:
                    simplified_data["actions"] = {
                        phase: [
                            {"id": a.id, "from": a.from_, "to": a.to, "L": a.L, "H": a.H, "R": a.R, "locked": a.locked}
                            for a in actions
                        ]
                        for phase, actions in result.game_state.actions.items()
                    }

                FileUtils.save_json(simplified_data, os.path.abspath("game_state.json"))

            # Save detailed debug results
            debug_data = {
                "timestamp": result.timestamp.isoformat(),
                "window_bounds": result.window_bounds,
                "rois_processed": result.rois_processed,
                "overall_success": result.overall_success,
                "success_rate": result.success_rate,
                "roi_results": {
                    roi_name: {
                        "coordinates": roi_result.roi_coordinates,
                        "extracted_data": self._serialize_extracted_data(roi_result.extracted_data),
                        "confidence": roi_result.confidence,
                        "success": roi_result.success,
                        "error_message": roi_result.error_message,
                        "raw_text": roi_result.raw_text,
                    }
                    for roi_name, roi_result in result.results.items()
                },
            }

            FileUtils.save_json(debug_data, os.path.abspath("debug_rois.json"))
            logger.info("Results saved to game_state.json and debug_rois.json")

        except Exception as e:
            logger.error(f"Failed to save results: {e}")

    def print_summary(self, result: ScreenReadingResult) -> None:
        """Print concise summary to console."""
        try:
            print("\n" + "=" * 50)
            print("RTS GAME STATE")
            print("=" * 50)

            if not result.game_state:
                print("[FAILED] No game state extracted")
                return

            # Basic info
            timestamp_str = result.timestamp.strftime("%H:%M:%S")
            ler_str = f"{result.game_state.ler.blue}:{result.game_state.ler.red}"
            print(
                f"{timestamp_str} | Phase: {result.game_state.phase} | LER: {ler_str} ({result.game_state.ler.favour})"
            )

            # Base information
            print("\nBASES:")
            for base_name, faction_units in result.game_state.bases.items():
                blue_total = faction_units.blue.total
                red_total = faction_units.red.total
                print(
                    f"  {base_name.upper()}: Blue({blue_total}) Red({red_total}) | "
                    f"B:L{faction_units.blue.light}H{faction_units.blue.heavy}R{faction_units.blue.ranged} "
                    f"R:L{faction_units.red.light}H{faction_units.red.heavy}R{faction_units.red.ranged}"
                )

            # Action information
            if result.game_state.actions:
                total_actions = result.game_state.total_actions
                if total_actions > 0:
                    print(f"\nACTIONS ({total_actions} total):")
                    for phase, actions in result.game_state.actions.items():
                        if actions:
                            print(f"  Phase {phase}:")
                            for action in actions:
                                status = "LOCKED" if action.locked else "UNLOCKED"
                                print(
                                    f"    {action.id}. {action.from_} -> {action.to}: L{action.L} H{action.H} R{action.R} [{status}]"
                                )

            # Processing statistics
            success_count = len([r for r in result.results.values() if r.success])
            print(f"\n[SUCCESS] ROIs: {success_count}/{result.rois_processed} successful")

        except Exception as e:
            logger.error(f"Failed to print summary: {e}")
            print(f"[ERROR] Failed to print summary: {e}")

    def _capture_game_screen(self):
        """Capture the game screen, returning window bounds and image."""
        try:
            window_bounds, screen_image = self.screen_capture.capture_target()

            if screen_image is None:
                logger.error("Failed to capture screen")
                return None, None

            logger.info(f"Screen capture successful: {window_bounds}")
            return window_bounds, screen_image

        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None, None

    def _process_standard_rois(self, screen_image, rois):
        """Process all standard ROI regions (non-action card)."""
        results = {}

        for roi_name, roi_coords in rois.items():
            try:
                results[roi_name] = self.process_single_roi(screen_image, roi_name, roi_coords)
            except Exception as e:
                logger.error(f"Error processing ROI {roi_name}: {e}")
                results[roi_name] = self._create_roi_result(roi_name, roi_coords, error_message=str(e))

        return results

    def _process_action_cards(self, screen_image):
        """Process action cards and return as ROI result."""
        logger.info("Processing action cards...")
        roi_coords = (0, 0, 1, 1)  # Full screen relative coords

        try:
            action_phases = self.action_card_processor.process_action_cards(screen_image)
            total_cards = sum(len(cards) for cards in action_phases.values())
            logger.info(f"Found {total_cards} action cards across phases")

            if total_cards > 0:
                # Flatten all cards and calculate average confidence
                all_cards = [card for phase_cards in action_phases.values() for card in phase_cards]
                avg_confidence = sum(card.confidence for card in all_cards) / len(all_cards)

                return {
                    "action_cards": self._create_roi_result(
                        "action_cards",
                        roi_coords,
                        {"phases": action_phases, "cards": all_cards},
                        avg_confidence,
                        True,
                        None,
                        f"Found {total_cards} action cards",
                    )
                }
            else:
                return {
                    "action_cards": self._create_roi_result(
                        "action_cards",
                        roi_coords,
                        {"phases": {"1": [], "2": [], "3": []}, "cards": []},
                        0.0,
                        False,
                        "No action cards detected",
                    )
                }

        except Exception as e:
            logger.error(f"Action card processing failed: {e}")
            return {
                "action_cards": self._create_roi_result("action_cards", roi_coords, {"cards": []}, 0.0, False, str(e))
            }

    def _process_phase_header(self, roi_name: str, roi_image, roi_coords: tuple) -> ROIResult:
        """Process phase header ROI."""
        phase, confidence = self.ocr_processor.read_phase(roi_image)
        return self._create_roi_result(
            roi_name, roi_coords, {"phase": phase}, confidence, phase > 0, None, f"Phase {phase}"
        )

    def _process_ler_panel(self, roi_name: str, roi_image, roi_coords: tuple) -> ROIResult:
        """Process LER panel ROI."""
        ler, confidence = self.ocr_processor.read_ler(roi_image)
        return self._create_roi_result(
            roi_name,
            roi_coords,
            {"blue_ratio": ler.blue, "red_ratio": ler.red, "favour": ler.favour},
            confidence,
            confidence > 0,
            None,
            ler.raw,
        )

    def _process_adjustment_cell(self, roi_name: str, roi_image, roi_coords: tuple) -> ROIResult:
        """Process adjustment cell ROI."""
        value, confidence = self.ocr_processor.read_adjustment_cell(roi_image, roi_name)
        return self._create_roi_result(
            roi_name, roi_coords, {"value": value}, confidence, confidence > 10, None, str(value)
        )

    def _create_roi_result(
        self,
        roi_name: str,
        roi_coords: tuple,
        extracted_data: Any = None,
        confidence: float = 0.0,
        success: bool = False,
        error_message: str = None,
        raw_text: str = None,
    ) -> ROIResult:
        """Helper to create ROIResult objects."""
        return ROIResult(
            roi_name=roi_name,
            roi_coordinates=roi_coords,
            extracted_data=extracted_data or {},
            confidence=confidence,
            success=success,
            error_message=error_message,
            raw_text=raw_text,
        )

    def _create_failed_result(self, timestamp: datetime, error_message: str) -> ScreenReadingResult:
        """Create a failed ScreenReadingResult."""
        logger.error(f"Creating failed result: {error_message}")
        return ScreenReadingResult(
            timestamp=timestamp,
            window_bounds=(),
            rois_processed=0,
            results={},
            overall_success=False,
        )

    def _cleanup_debug_files(self) -> None:
        """Clean up debug images from previous runs."""
        try:
            if self.debug_utils.auto_cleanup:
                FileUtils.cleanup_old_files("roi_captures", "*.png", 24)  # 24 hours
        except Exception as e:
            logger.warning(f"Debug cleanup failed: {e}")

    def _serialize_extracted_data(self, extracted_data: Any) -> Any:
        """Convert extracted data to JSON-serializable format."""
        import numpy as np

        def convert_value(value):
            if isinstance(value, np.floating):
                return float(value)
            elif isinstance(value, np.integer):
                return int(value)
            elif isinstance(value, np.ndarray):
                return f"<{type(value).__name__}: {value.shape}>"
            elif hasattr(value, "from_faction"):  # ActionCard object
                return {
                    "from_faction": convert_value(value.from_faction),
                    "to_faction": convert_value(value.to_faction),
                    "light_count": convert_value(value.light_count),
                    "heavy_count": convert_value(value.heavy_count),
                    "ranged_count": convert_value(value.ranged_count),
                    "is_locked": convert_value(value.is_locked),
                    "confidence": convert_value(value.confidence),
                    "raw_text": convert_value(value.raw_text),
                }
            elif isinstance(value, dict):
                return {k: convert_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [convert_value(item) for item in value]
            else:
                return value

        serialized = {}
        for key, value in extracted_data.items():
            if key == "raw_crop":
                serialized[key] = f"<Image array: {type(value).__name__}>"
            else:
                serialized[key] = convert_value(value)

        return serialized
