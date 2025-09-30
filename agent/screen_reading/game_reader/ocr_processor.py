# OCR processing and color detection for live game reading
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from core.models import ROIMeta, OCRResult
from imaging.utils import ImageUtils


class GameOCRProcessor:  # Handles OCR processing and color detection for game reading

    def __init__(self, ocr_processor, screen_capture, output_manager):
        self.ocr_processor = ocr_processor
        self.screen_capture = screen_capture
        self.output_manager = output_manager
        # Thread pool for parallel OCR processing
        self.max_workers = 8  # Configurable number of parallel workers

    def _display_roi_processing_results(self, roi_name: str, results: List[Tuple], final_result: OCRResult):
        # Enhanced output showing processing attempts and final result
        if not results:
            print(f"    {roi_name}: No results from OCR processing")
            return

        # Show top 3 processing attempts
        print(f"    {roi_name} processing attempts:")
        for i, (method_name, _, text, confidence, rule_passed, rule_message) in enumerate(results[:3]):
            status = "[PASS]" if rule_passed else "[FAIL]"
            text_display = f"'{text}'" if text else "''"
            print(f"      #{i+1}: {text_display} ({confidence:.1f}%) from {method_name} {status}")

        if len(results) > 3:
            print(f"      ... and {len(results) - 3} more attempts")

        # Show final selected result with timing
        status = "[PASS]" if final_result.rule_passed else "[FAIL]"
        text_display = f"'{final_result.text}'" if final_result.text else "''"
        timing_display = f"({final_result.processing_time_ms:.0f}ms)" if final_result.processing_time_ms > 0 else ""
        print(
            f"    FINAL: {text_display} ({final_result.confidence:.1f}%, {final_result.processing_time_ms:.0f}ms) from {final_result.method_used} {status}"
        )
        print(f"    {roi_name}: {final_result.text or '0'}")

    def _process_single_roi(self, roi_name: str, roi: ROIMeta, frame: Image.Image, phase_num: int, is_adjustment: bool = False) -> Tuple[str, OCRResult, Optional[List]]:
        """Process a single ROI - designed to be called in parallel"""
        # Crop ROI from frame
        roi_image = ImageUtils.crop_roi(frame, roi)

        # For adjustment ROIs, check if content exists
        if is_adjustment:
            has_content = self.has_content(roi_image)
            if not has_content:
                # No adjustment = 0, skip OCR processing
                return roi_name, OCRResult(
                    text="0",
                    confidence=100.0,
                    method_used="No content detected",
                    rule_passed=True,
                    rule_message="No adjustment needed",
                    processing_time_ms=0
                ), None

        # Save debug image
        self.output_manager.save_capture(roi_image, phase_num, roi_name)

        # Process OCR with timing - respect engine preferences
        accepted_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-:. "
        start_time = time.time()

        # Check preferred OCR engine from ROI settings
        if roi.preferred_ocr_engine == "auto":
            # Use multi-engine processing (tries all engines with early exit)
            results = self.ocr_processor.process_multi_engine(
                roi_image, roi, accepted_chars=accepted_chars, early_exit_enabled=True
            )
        elif roi.preferred_ocr_engine in ["tesseract", "paddle_gpu", "paddle_cpu"]:
            # Use specific engine as requested
            results = self.ocr_processor.process_single_engine(
                roi_image, roi, roi.preferred_ocr_engine,
                accepted_chars=accepted_chars, early_exit_enabled=True
            )
        else:
            # Fallback to multi-engine if unknown preference
            results = self.ocr_processor.process_multi_engine(
                roi_image, roi, accepted_chars=accepted_chars, early_exit_enabled=True
            )

        processing_time_ms = (time.time() - start_time) * 1000

        if results:
            # Get the best result (first one due to early exit)
            method_name, _, text, confidence, rule_passed, rule_message = results[0]
            ocr_result = OCRResult(
                text=text,
                confidence=confidence,
                method_used=method_name,
                rule_passed=rule_passed,
                rule_message=rule_message,
                processing_time_ms=processing_time_ms,
            )
        else:
            ocr_result = OCRResult(
                text="",
                confidence=0.0,
                method_used="Full matrix failed",
                rule_passed=False,
                rule_message="No results",
                processing_time_ms=processing_time_ms,
            )

        # Apply colour-based sign correction for adjustments if needed
        if is_adjustment and not ocr_result.rule_passed and ocr_result.text.strip():
            if ocr_result.text.strip().isdigit():
                has_content, dominant_colour = self.get_content_and_colour(roi_image)

                if has_content and dominant_colour in ["red", "green"]:
                    # Add appropriate sign based on colour
                    if dominant_colour == "red":
                        corrected_text = f"-{ocr_result.text.strip()}"
                    else:  # green
                        corrected_text = f"+{ocr_result.text.strip()}"

                    # Re-validate with the corrected text
                    rule_passed, rule_message = self.ocr_processor.validator.validate_text(roi, corrected_text)

                    if rule_passed:
                        ocr_result.text = corrected_text
                        ocr_result.rule_passed = True
                        ocr_result.rule_message = f"Color-corrected: {rule_message}"
                        ocr_result.method_used = f"{ocr_result.method_used} (colour-corrected)"
                        logging.info(f"Color correction applied to {roi_name}: '{ocr_result.text}' (detected {dominant_colour} pixels)")

        return roi_name, ocr_result, results

    def process_phase_ocr(
        self, phase_num: int, monitor_index: int, base_unit_rois: Dict[str, ROIMeta], adjustment_rois: Dict[str, ROIMeta]
    ) -> Dict[str, Any]:
        # Process OCR for all units and adjustments in a phase using parallel processing
        phase_start_time = time.time()
        print(f"\n=== Processing Phase {phase_num} OCR (Parallel) ===")
        logging.info(f"Starting Phase {phase_num} OCR processing with {self.max_workers} workers")

        # Capture single frame
        frame = self.screen_capture.capture_monitor(monitor_index)
        if frame is None:
            print("Failed to capture screen")
            return {}

        ocr_results = {}

        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks to the executor
            futures = {}

            # Submit base unit ROI tasks
            for roi_name, roi in base_unit_rois.items():
                future = executor.submit(self._process_single_roi, roi_name, roi, frame, phase_num, False)
                futures[future] = ('base', roi_name)

            # Submit adjustment ROI tasks
            for roi_name, roi in adjustment_rois.items():
                future = executor.submit(self._process_single_roi, roi_name, roi, frame, phase_num, True)
                futures[future] = ('adj', roi_name)

            # Collect results as they complete
            print("  Processing ROIs in parallel...")
            base_results = []
            adj_results = []

            for future in as_completed(futures):
                roi_type, original_name = futures[future]
                try:
                    roi_name, ocr_result, results = future.result()

                    # Store result
                    ocr_results[roi_name] = ocr_result.text if ocr_result.text else "0"

                    # Log result
                    if ocr_result.text or roi_type == 'base':
                        logging.info(f"Phase {phase_num} - {roi_name}: '{ocr_result.text}' ({ocr_result.confidence:.1f}%)")

                    # Store for display later
                    if roi_type == 'base':
                        base_results.append((roi_name, ocr_result, results))
                    else:
                        if ocr_result.text != "0" or (ocr_result.text == "0" and ocr_result.method_used != "No content detected"):
                            adj_results.append((roi_name, ocr_result, results))

                except Exception as e:
                    logging.error(f"Error processing {original_name}: {e}")
                    ocr_results[original_name] = "0"

        # Display results in organized fashion
        if base_results:
            print("  Base unit counts:")
            for roi_name, ocr_result, results in sorted(base_results, key=lambda x: x[0]):
                if results is not None:
                    self._display_roi_processing_results(roi_name, results, ocr_result)
                else:
                    print(f"    {roi_name}: {ocr_result.text or '0'}")

        if adj_results:
            print("  Adjustment values:")
            for roi_name, ocr_result, results in sorted(adj_results, key=lambda x: x[0]):
                if ocr_result.text:
                    if results is not None:
                        self._display_roi_processing_results(roi_name, results, ocr_result)
                    else:
                        print(f"    {roi_name}: {ocr_result.text}")
                else:
                    # Content detected but OCR failed
                    logging.warning(f"{roi_name}: Color content detected but OCR returned empty")
                    print(f"    {roi_name}: Content detected but OCR failed")

        # Log phase completion timing
        phase_duration = time.time() - phase_start_time
        logging.info(f"Phase {phase_num} completed in {phase_duration:.2f}s ({len(ocr_results)} ROIs processed in parallel)")
        print(f"Phase {phase_num} processing completed in {phase_duration:.2f}s")

        return ocr_results

    def has_content(self, roi_image: Image.Image) -> bool:
        # Check if adjustment ROI contains red or green pixels
        try:
            # Convert to RGB if needed
            if roi_image.mode != "RGB":
                rgb_image = roi_image.convert("RGB")
            else:
                rgb_image = roi_image

            width, height = rgb_image.size
            red_pixels = 0
            green_pixels = 0

            # Sample pixels to detect red or green text (sample every 2nd pixel for speed)
            for x in range(0, width, 2):
                for y in range(0, height, 2):
                    r, g, b = rgb_image.getpixel((x, y))

                    # Red detection for negative adjustments
                    if r > 150 and g < 100 and b < 100:
                        red_pixels += 1

                    # Green detection for positive adjustments
                    elif g > 150 and r < 100 and b < 100:
                        green_pixels += 1

            # Minimum threshold of coloured pixels to confirm content exists
            min_threshold = 10  # Adjustable based on ROI size
            has_content = (red_pixels >= min_threshold) or (green_pixels >= min_threshold)

            if has_content:
                colour_type = "red" if red_pixels > green_pixels else "green"
                logging.debug(f"Adjustment ROI has {colour_type} content " f"(R:{red_pixels}, G:{green_pixels} pixels)")

            return has_content

        except Exception as e:
            logging.warning(f"Error checking adjustment content: {e}")
            return True  # Assume content exists on error

    def get_content_and_colour(self, roi_image: Image.Image) -> tuple[bool, str]:
        # Detect red/green pixels to determine adjustment sign (+/-) and presence of content
        try:
            # Convert to RGB if needed
            if roi_image.mode != "RGB":
                rgb_image = roi_image.convert("RGB")
            else:
                rgb_image = roi_image

            width, height = rgb_image.size
            red_pixels = 0
            green_pixels = 0

            # Sample pixels to detect red or green text (sample every 2nd pixel for speed)
            for x in range(0, width, 2):
                for y in range(0, height, 2):
                    r, g, b = rgb_image.getpixel((x, y))

                    # Red detection for negative adjustments
                    if r > 150 and g < 100 and b < 100:
                        red_pixels += 1

                    # Green detection for positive adjustments
                    elif g > 150 and r < 100 and b < 100:
                        green_pixels += 1

            # Minimum threshold of coloured pixels to confirm content exists
            min_threshold = 10  # Adjustable based on ROI size
            has_content = (red_pixels >= min_threshold) or (green_pixels >= min_threshold)

            if has_content:
                dominant_colour = "red" if red_pixels > green_pixels else "green"
                logging.debug(f"Adjustment ROI has {dominant_colour} content (R:{red_pixels}, G:{green_pixels} pixels)")
                return has_content, dominant_colour
            else:
                return False, "none"

        except Exception as e:
            logging.warning(f"Error checking adjustment colour: {e}")
            return True, "none"  # Assume content exists but unknown colour on error