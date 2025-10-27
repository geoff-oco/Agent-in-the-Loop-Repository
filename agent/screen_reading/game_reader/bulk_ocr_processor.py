# Bulk OCR processor for efficient batch processing with mode support
import logging
import os
from typing import Dict, Optional
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed


class BulkOCRProcessor:
    def __init__(self, game_ocr_processor, progress_reporter=None, max_workers=None):
        # Auto-configure workers if not specified: default 4, scaled by CPU count with min 2
        if max_workers is None:
            max_workers = min(4, max(2, os.cpu_count() or 2))
        self.game_ocr = game_ocr_processor  # Reuse existing GameOCRProcessor with all its logic
        self.progress_reporter = progress_reporter
        self.max_workers = max_workers
        self.completed_tasks = 0  # Track completed tasks across all processing
        self.total_tasks = 0  # Will be set when processing starts

    def _select_best_with_confidence_weighting(self, results_with_confidence: list) -> str:
        # Select best OCR result using confidence-weighted voting
        # Input: [(value, confidence), ...] from multiple frames
        # Returns: The value with highest total confidence across all frames
        if not results_with_confidence:
            return "0"

        # Group results by value and collect confidences
        value_scores = {}
        for value, confidence in results_with_confidence:
            if value not in value_scores:
                value_scores[value] = []
            value_scores[value].append(confidence)

        # Calculate total confidence for each unique value
        weighted_scores = {value: sum(confidences) for value, confidences in value_scores.items()}

        # Safety check: if no valid scores, return default
        if not weighted_scores:
            logging.warning("[BulkOCR] No valid confidence scores for Red2 final selection")
            return "0"

        # Select value with highest total confidence
        best_value = max(weighted_scores, key=weighted_scores.get)

        # Log the selection process
        print(f"  Confidence weighting breakdown:")
        for value, confidences in sorted(value_scores.items()):
            total_conf = sum(confidences)
            count = len(confidences)
            avg_conf = total_conf / count if count > 0 else 0
            print(f"    Value {value}: appears {count}x, total confidence={total_conf:.1f}, avg={avg_conf:.1f}%")
        print(f"  > Selected: {best_value} (highest total confidence)")

        return str(best_value)

    def process_bulk_captures(
        self,
        captured_screenshots: Dict[int, Image.Image],
        phase_modes: Dict[int, str],
        base_unit_rois: Dict,
        adjustment_rois: Dict,
        total_ocr_tasks: int = 0,
    ) -> Dict[int, Dict]:
        # Process each screenshot according to mode
        # "full" -> process base + adjustments
        # "before_only" -> process base only (skip adjustments)
        # Return: {phase_num: {roi_name: text}, ...}

        print("\n=== Bulk OCR Processing ===")
        print(f"Processing {len(captured_screenshots)} phase screenshots")
        print(f"Phase modes: {phase_modes}")

        # Set total tasks for progress tracking (includes LER + phases + Red2)
        self.total_tasks = total_ocr_tasks if total_ocr_tasks > 0 else 0
        # Start counting from 1 (LER already completed)
        self.completed_tasks = 1

        results = {}

        # Build task list for all OCR operations
        ocr_tasks = []
        for phase_num, screenshot in captured_screenshots.items():
            mode = phase_modes.get(phase_num, "full")

            # Always need base unit counts - use actual ROI names from template
            for roi_name, roi in base_unit_rois.items():
                ocr_tasks.append(
                    {
                        "phase": phase_num,
                        "category": "base",
                        "roi_name": roi_name,
                        "roi": roi,
                        "screenshot": screenshot,
                    }
                )

            # Only process adjustments if mode is "full"
            if mode == "full":
                for roi_name, roi in adjustment_rois.items():
                    ocr_tasks.append(
                        {
                            "phase": phase_num,
                            "category": "adjustment",
                            "roi_name": roi_name,
                            "roi": roi,
                            "screenshot": screenshot,
                        }
                    )

        print(f"\nTotal phase OCR tasks queued: {len(ocr_tasks)}")

        # Process all OCR tasks in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {executor.submit(self._process_single_roi, task): task for task in ocr_tasks}

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    ocr_text = future.result()

                    # Initialize phase result dict if needed (flat structure like old code)
                    if task["phase"] not in results:
                        results[task["phase"]] = {}

                    # Store result with ROI name as key (flat dict structure)
                    results[task["phase"]][task["roi_name"]] = ocr_text if ocr_text else "0"

                    self.completed_tasks += 1

                    # Update progress using total OCR tasks (LER + phases + Red2)
                    if self.progress_reporter and self.completed_tasks % 5 == 0 and self.total_tasks > 0:
                        percentage = 25 + int((self.completed_tasks / self.total_tasks) * 70)
                        self.progress_reporter.update(
                            f"OCR processing: {self.completed_tasks}/{self.total_tasks} tasks complete",
                            percentage=percentage,
                        )

                except Exception as e:
                    logging.error(f"[BulkOCR] Phase {task['phase']} {task['roi_name']} failed: {e}")
                    # Store default "0" on failure
                    if task["phase"] not in results:
                        results[task["phase"]] = {}
                    results[task["phase"]][task["roi_name"]] = "0"

        print(f"\nPhase OCR processing complete: {len(ocr_tasks)} tasks processed")

        return results

    def process_red2_final_screenshots(self, screenshots: list, red2_final_roi) -> Optional[str]:
        # Process 5 screenshots for red2 final count with confidence-weighted selection
        # Red2 final is SINGLE NUMBER (total unit count), not L/H/R breakdown
        # Return: Confidence-weighted OCR text result as string (e.g. "15") or None

        if not screenshots or len(screenshots) == 0:
            logging.warning("[BulkOCR] No Red2 final screenshots to process")
            return None

        if not red2_final_roi:
            logging.warning("[BulkOCR] No Red2 final ROI provided")
            return None

        print(f"\n=== Processing Red2 Final Count ({len(screenshots)} frames) ===")

        # Process each screenshot's red2 ROI and collect valid results WITH confidence
        results_with_confidence = []

        for i, screenshot in enumerate(screenshots):
            try:
                # Import ImageUtils for proper ROI cropping
                from imaging.utils import ImageUtils

                # Crop ROI using ImageUtils (same as GameOCRProcessor does)
                roi_image = ImageUtils.crop_roi(screenshot, red2_final_roi)

                # Save capture to final_state folder
                if hasattr(self.game_ocr, "output_manager") and self.game_ocr.output_manager:
                    self.game_ocr.output_manager.save_capture(
                        roi_image, phase_num="final_state", roi_name=f"Red2_Final_Capture_{i+1}"
                    )

                # Process OCR using process_multi_engine (like old code)
                accepted_chars = "0123456789"
                results = self.game_ocr.ocr_processor.process_multi_engine(
                    roi_image, red2_final_roi, accepted_chars=accepted_chars, early_exit_enabled=True
                )

                if results:
                    # Get best result (highest confidence from this frame)
                    method_name, _, text, confidence, rule_passed, rule_message = results[0]

                    # Only use valid digit results
                    if text.strip() and text.strip().isdigit():
                        value = int(text.strip())
                        # Store both value AND confidence for weighted selection
                        results_with_confidence.append((value, confidence))
                        print(f"  Frame {i+1}: '{text}' ({confidence:.1f}%, {method_name})")
                    else:
                        print(f"  Frame {i+1}: Invalid text '{text}'")
                else:
                    print(f"  Frame {i+1}: No OCR results")

                # Update progress for each Red2 frame processed
                self.completed_tasks += 1
                if self.progress_reporter and self.total_tasks > 0:
                    percentage = 25 + int((self.completed_tasks / self.total_tasks) * 70)
                    self.progress_reporter.update(
                        f"OCR processing: {self.completed_tasks}/{self.total_tasks} tasks complete",
                        percentage=percentage,
                    )

            except Exception as e:
                logging.error(f"[BulkOCR] Red2 final frame {i+1} OCR failed: {e}")

        # Select best result using confidence-weighted voting
        if results_with_confidence:
            result_str = self._select_best_with_confidence_weighting(results_with_confidence)
            print(f"Red2 Final Result: {result_str}")
            return result_str
        else:
            logging.warning("[BulkOCR] No valid Red2 final OCR results")
            return None

    def _process_single_roi(self, task: Dict) -> Optional[str]:
        # Helper method to process a single ROI OCR task
        # Reuses GameOCRProcessor logic for proper OCR with validation
        # Returns: OCR text result or None

        try:
            screenshot = task["screenshot"]  # Full screenshot
            roi = task["roi"]
            phase_num = task["phase"]
            roi_name = task["roi_name"]
            is_adjustment = task["category"] == "adjustment"

            # Pass full screenshot to GameOCRProcessor - it will handle ROI cropping internally
            # GameOCRProcessor._process_single_roi expects full frame and crops using ImageUtils.crop_roi()
            _, ocr_result, _ = self.game_ocr._process_single_roi(roi_name, roi, screenshot, phase_num, is_adjustment)

            # Return the OCR text result
            return ocr_result.text if ocr_result else None

        except Exception as e:
            logging.error(f"[BulkOCR] Failed to process ROI {task.get('roi_name', 'unknown')}: {e}")
            return None
