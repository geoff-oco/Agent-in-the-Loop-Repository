# OCR processing and colour detection for live game reading
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from core.models import ROIMeta, OCRResult
from imaging.utils import ImageUtils


class GameOCRProcessor:  # Handles OCR processing and colour detection for game reading

    def __init__(self, ocr_processor, screen_capture, output_manager):
        self.ocr_processor = ocr_processor
        self.screen_capture = screen_capture
        self.output_manager = output_manager
        # Thread pool for parallel OCR processing (auto-configured: default 4, min 2)
        self.max_workers = min(4, max(2, os.cpu_count() or 2))

    def _process_single_roi(
        self, roi_name: str, roi: ROIMeta, frame: Image.Image, phase_num: int, is_adjustment: bool = False
    ) -> Tuple[str, OCRResult, Optional[List]]:
        # Process a single ROI with parallel execution support - returns ROI name, OCR result, and processing details
        # Crop ROI from frame
        roi_image = ImageUtils.crop_roi(frame, roi)

        # For adjustment ROIs, check if content exists
        if is_adjustment:
            has_content, _ = self.detect_adjustment_colour(roi_image)
            if not has_content:
                # No adjustment = 0, skip OCR processing
                return (
                    roi_name,
                    OCRResult(
                        text="0",
                        confidence=100.0,
                        method_used="No content detected",
                        rule_passed=True,
                        rule_message="No adjustment needed",
                        processing_time_ms=0,
                    ),
                    None,
                )

        # Save debug image
        self.output_manager.save_capture(roi_image, phase_num, roi_name)

        # Process OCR with timing - respect engine preferences
        accepted_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-:. "
        start_time = time.time()

        # Always use multi-engine processing which:
        # - Respects preferred_ocr_engine from ROI settings
        # - Tries preferred engine first with all preprocessing methods
        # - Early exits if high confidence result passes validation
        # - Falls back to other engines/methods if needed
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
                has_content, dominant_colour = self.detect_adjustment_colour(roi_image)

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
                        ocr_result.rule_message = f"Colour-corrected: {rule_message}"
                        ocr_result.method_used = f"{ocr_result.method_used} (colour-corrected)"
                        logging.info(
                            f"[Phase {phase_num}] Colour correction applied to {roi_name}: '{ocr_result.text}' (detected {dominant_colour} pixels)"
                        )

        return roi_name, ocr_result, results

    def detect_adjustment_colour(self, roi_image: Image.Image) -> tuple[bool, str]:
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
