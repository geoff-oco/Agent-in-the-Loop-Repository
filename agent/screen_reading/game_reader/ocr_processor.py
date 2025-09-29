# OCR processing and color detection for live game reading
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from core.models import ROIMeta, OCRResult
from imaging.utils import ImageUtils


class GameOCRProcessor:  # Handles OCR processing and color detection for game reading

    def __init__(self, ocr_processor, screen_capture, output_manager):
        self.ocr_processor = ocr_processor
        self.screen_capture = screen_capture
        self.output_manager = output_manager

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

    def process_phase_ocr(
        self, phase_num: int, monitor_index: int, base_unit_rois: Dict[str, ROIMeta], adjustment_rois: Dict[str, ROIMeta]
    ) -> Dict[str, Any]:
        # Process OCR for all units and adjustments in a phase
        phase_start_time = time.time()
        print(f"\n=== Processing Phase {phase_num} OCR ===")
        logging.info(f"Starting Phase {phase_num} OCR processing")

        # Capture single frame
        frame = self.screen_capture.capture_monitor(monitor_index)
        if frame is None:
            print("Failed to capture screen")
            return {}

        ocr_results = {}

        # Process all base unit ROIs
        print("  Base unit counts:")
        for roi_name, roi in base_unit_rois.items():
            # Crop ROI from frame
            roi_image = ImageUtils.crop_roi(frame, roi)

            # Save debug image using session manager
            self.output_manager.save_capture(roi_image, phase_num, roi_name)

            # Process OCR using multi-engine processing with timing
            accepted_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-:. "
            start_time = time.time()
            results = self.ocr_processor.process_multi_engine(
                roi_image, roi, accepted_chars=accepted_chars, early_exit_enabled=True
            )
            processing_time_ms = (time.time() - start_time) * 1000  # Convert to milliseconds

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

            # Store result
            ocr_results[roi_name] = ocr_result.text if ocr_result.text else "0"

            # Log result
            logging.info(f"Phase {phase_num} - {roi_name}: '{ocr_result.text}' " f"({ocr_result.confidence:.1f}%)")

            # Enhanced output showing processing attempts and final result
            self._display_roi_processing_results(roi_name, results, ocr_result)

        # Process all adjustment ROIs
        print("  Adjustment values:")
        for roi_name, roi in adjustment_rois.items():
            # Crop ROI from frame
            roi_image = ImageUtils.crop_roi(frame, roi)

            # Check if ROI has red/green content first
            has_content = self.has_content(roi_image)

            if not has_content:
                ocr_results[roi_name] = "0"  # No adjustment = 0
                logging.debug(f"{roi_name}: No red/green pixels detected - treating as 0")
                # Don't print anything for empty adjustment ROIs
                continue

            # Save debug image (only if content detected)
            self.output_manager.save_capture(roi_image, phase_num, roi_name)

            # Process OCR only if content detected with timing
            accepted_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-:. "
            start_time = time.time()
            results = self.ocr_processor.process_multi_engine(
                roi_image, roi, accepted_chars=accepted_chars, early_exit_enabled=True
            )
            processing_time_ms = (time.time() - start_time) * 1000  # Convert to milliseconds

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

            # Apply colour-based sign correction if pattern validation failed
            if not ocr_result.rule_passed and ocr_result.text.strip():
                # Check if the text is just a number without sign
                if ocr_result.text.strip().isdigit():
                    # Get colour information from the ROI
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
                            # Update the OCR result with corrected text
                            ocr_result.text = corrected_text
                            ocr_result.rule_passed = True
                            ocr_result.rule_message = f"Color-corrected: {rule_message}"
                            ocr_result.method_used = f"{ocr_result.method_used} (colour-corrected)"
                            logging.info(
                                f"Color correction applied to {roi_name}: '{ocr_result.text}' (detected {dominant_colour} pixels)"
                            )

            # Store result
            ocr_results[roi_name] = ocr_result.text if ocr_result.text else "0"

            # Log result with raw OCR text and pattern validation
            if ocr_result.text:
                logging.info(
                    f"Phase {phase_num} - {roi_name}: '{ocr_result.text}' "
                    f"(confidence: {ocr_result.confidence:.1f}%)"
                )
                # Enhanced output showing processing attempts and final result
                self._display_roi_processing_results(roi_name, results, ocr_result)
            else:
                # Content detected but OCR failed
                logging.warning(f"{roi_name}: Color content detected but OCR returned empty")
                print(f"    {roi_name}: Content detected but OCR failed")

        # Log phase completion timing
        phase_duration = time.time() - phase_start_time
        logging.info(f"Phase {phase_num} completed in {phase_duration:.2f}s ({len(ocr_results)} ROIs processed)")
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