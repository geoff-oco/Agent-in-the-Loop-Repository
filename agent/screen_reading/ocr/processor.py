# OCR processing pipeline coordinating preprocessing and recognition with multi-engine support
from typing import List, Tuple, Optional, Dict
from PIL import Image
import time
import logging

from core.models import ROIMeta, OCRResult, ProcessingMethod
from core.validators import get_text_validator
from imaging.preprocessor import ImagePreprocessor
from ocr.paddle_engine import get_paddle_engine
from ocr.tesseract_engine import get_tesseract_engine
from ocr.engine_selector import get_engine_selector, EngineType


class OCRConfig:  # Configuration constants for OCR processing
    # Confidence thresholds
    EARLY_EXIT_CONFIDENCE = 90.0
    EXCELLENT_CONFIDENCE = 92.0
    FALLBACK_HIGH_CONFIDENCE = 95.0

    # Scoring weights
    PATTERN_MATCH_SCORE = 100
    PATTERN_FAILURE_PENALTY = -50
    NON_EMPTY_BONUS = 10
    MAX_CONTENT_BONUS = 5

    # Image processing
    SCALE_THRESHOLD = 0.01


class OCRProcessor:  # Coordinates image preprocessing and OCR recognition with multi-engine support.
    # Handles both multi-candidate processing (for UI) and optimised single-method processing (for agents).

    def __init__(self):
        self.preprocessor = ImagePreprocessor()
        self.paddle_engine = get_paddle_engine()
        self.tesseract_engine = get_tesseract_engine()  # Add Tesseract support
        self.engine_selector = get_engine_selector()  # Add engine selection
        self.validator = get_text_validator()

    def _get_filters(  # Extract whitelist/blacklist settings from ROI metadata
        self, roi_meta: ROIMeta, accepted_chars: Optional[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        char_filter = getattr(roi_meta, "char_filter", "")
        filter_mode = getattr(roi_meta, "filter_mode", "whitelist")

        if char_filter and filter_mode == "whitelist":
            return char_filter, None
        elif char_filter and filter_mode == "blacklist":
            return accepted_chars, char_filter
        else:
            return accepted_chars, None

    def _run_ocr(
        self,
        image: Image.Image,
        engine_type: EngineType,
        engine_instance: object,
        whitelist: Optional[str],
        blacklist: Optional[str],
        early_exit_enabled: bool = False,
        roi_meta: Optional[object] = None,
    ) -> Tuple[str, float, float]:  # Run OCR with the specified engine
        if engine_type == EngineType.PADDLE_GPU:
            return engine_instance.recognise_text(
                image, whitelist, blacklist, prefer_gpu=True, early_exit_enabled=early_exit_enabled, roi_meta=roi_meta
            )
        elif engine_type == EngineType.PADDLE_CPU:
            return engine_instance.recognise_text(
                image, whitelist, blacklist, prefer_gpu=False, early_exit_enabled=early_exit_enabled, roi_meta=roi_meta
            )
        elif engine_type == EngineType.TESSERACT:
            return engine_instance.recognise_text(
                image, whitelist, blacklist, early_exit_enabled=early_exit_enabled, roi_meta=roi_meta
            )
        else:
            # Default to PaddleOCR
            return self.paddle_engine.recognise_text(image, whitelist, blacklist)

    def _process_candidate_with_engine(
        self,
        processed_img: Image.Image,
        method_name: str,
        selected_engine: EngineType,
        engine_instance: object,
        whitelist: Optional[str],
        blacklist: Optional[str],
        roi_meta: ROIMeta,
        early_exit_enabled: bool,
    ) -> Tuple[str, float, bool, str, float]:
        # Process a single preprocessing candidate with specified engine
        text, confidence, scale_used = self._run_ocr(
            processed_img, selected_engine, engine_instance, whitelist, blacklist, early_exit_enabled, roi_meta
        )

        rule_passed, rule_message = self.validator.validate_text(roi_meta, text)
        score = self.calculate_unified_score(text, confidence, rule_passed)

        return text, confidence, rule_passed, rule_message, score

    def _get_fallback_result(
        self,
        image: Image.Image,
        selected_engine: EngineType,
        engine_instance: object,
        whitelist: Optional[str],
        blacklist: Optional[str],
        roi_meta: ROIMeta,
    ) -> Tuple[str, float, bool, str]:
        # Get fallback result using Enhanced preprocessing method
        processed_img = self.preprocessor.process_single(image, ProcessingMethod.ENHANCED)
        text, confidence, scale_used = self._run_ocr(
            processed_img, selected_engine, engine_instance, whitelist, blacklist
        )
        rule_passed, rule_message = self.validator.validate_text(roi_meta, text)
        return text, confidence, rule_passed, rule_message

    def _auto_select_best_method(
        self,
        image: Image.Image,
        roi_meta: ROIMeta,
        accepted_chars: Optional[str],
        start_time: float,
        selected_engine: EngineType,
        early_exit_enabled: bool = False,
    ) -> OCRResult:
        # Intelligent auto-selection: try all methods and pick the best one
        candidates = self.preprocessor.create_candidates(image)
        engine_instance = self.engine_selector.get_engine_instance(selected_engine)
        whitelist, blacklist = self._get_filters(roi_meta, accepted_chars)

        best_result = None
        best_score = -1
        best_method = "Enhanced"  # Fallback

        for method_name, processed_img in candidates:
            text, confidence, rule_passed, rule_message, score = self._process_candidate_with_engine(
                processed_img,
                method_name,
                selected_engine,
                engine_instance,
                whitelist,
                blacklist,
                roi_meta,
                early_exit_enabled,
            )

            # Track the best result
            if score > best_score:
                best_score = score
                best_method = method_name
                best_result = (text, confidence, rule_passed, rule_message)

            # ROI-level early exit: stop processing remaining methods if we got excellent results
            if early_exit_enabled and confidence > OCRConfig.EXCELLENT_CONFIDENCE and rule_passed:
                print(
                    f"    ROI early exit triggered: {confidence:.1f}% confidence + pattern match - skipping remaining methods"
                )
                break

        # If no results, fallback to Enhanced method
        if best_result is None:
            best_result = self._get_fallback_result(
                image, selected_engine, engine_instance, whitelist, blacklist, roi_meta
            )
            best_method = "Enhanced"

        text, confidence, rule_passed, rule_message = best_result
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        engine_method_name = f"Auto-Select ({selected_engine.value}_{best_method})"

        return OCRResult(
            text=text,
            confidence=confidence,
            method_used=engine_method_name,
            rule_passed=rule_passed,
            rule_message=rule_message,
            processing_time_ms=processing_time,
        )

    def get_available_engines(self) -> List[str]:  # Get list of available OCR engines
        return self.engine_selector.get_available_engines()

    def is_gpu_available(self) -> bool:  # Check if GPU acceleration is available
        return self.engine_selector.is_gpu_available()

    @property
    def available(self) -> bool:  # Check if OCR processing is available
        return (self.paddle_engine.available or self.tesseract_engine.available) and self.preprocessor.methods_available

    def _test_engines(  # Test all available engines on a single processed image
        self,
        processed_img: Image.Image,
        roi_meta: ROIMeta,
        whitelist: Optional[str],
        blacklist: Optional[str],
        early_exit_enabled: bool = False,
    ) -> List[Tuple[str, Image.Image, str, float, bool, str]]:
        # Test all available engines on a preprocessed image and return scored results
        results = []

        # Initialize validator for early exit if enabled
        validator = None
        if early_exit_enabled:
            validator = self.validator

        # Test available engines using centralized engine selection
        engines_to_test = []
        if self.tesseract_engine.available:
            engines_to_test.append("tesseract")
        if self.paddle_engine.available:
            engines_to_test.append("auto")  # Will select GPU/CPU automatically

        for engine_preference in engines_to_test:
            engine_name, text, confidence, scale_used = self._select_and_run_engine(
                engine_preference, processed_img, whitelist, blacklist, early_exit_enabled, roi_meta
            )

            rule_passed, rule_message = self.validator.validate_text(roi_meta, text)
            scaled_display = self._scale_display_image(processed_img, scale_used)
            results.append((engine_name, scaled_display, text, confidence, rule_passed, rule_message))

            # Don't early exit in multi-engine comparison - let all engines compete
            # Early exit logic is handled at the end after collecting all results

        # Return unsorted results - sorting will be handled by the calling method (process_multi_engine)

        return results

    def _scale_display_image(self, image: Image.Image, scale_used: float) -> Image.Image:
        # Scale image for display if needed, using consistent resampling
        if abs(scale_used - 1.0) > OCRConfig.SCALE_THRESHOLD:
            new_size = (int(image.width * scale_used), int(image.height * scale_used))
            return image.resize(new_size, Image.Resampling.LANCZOS)
        return image

    def _select_and_run_engine(
        self,
        engine_preference: str,
        processed_img: Image.Image,
        whitelist: Optional[str],
        blacklist: Optional[str],
        early_exit_enabled: bool,
        roi_meta: Optional[object],
    ) -> Tuple[str, str, float, float]:
        # Centralized engine selection and execution logic
        if engine_preference.lower() == "tesseract":
            if not self.tesseract_engine.available:
                return "Tesseract (unavailable)", "", 0.0, 1.0

            text, confidence, scale_used = self.tesseract_engine.recognise_text(
                processed_img, whitelist, blacklist, early_exit_enabled=early_exit_enabled, roi_meta=roi_meta
            )
            return "Tesseract", text, confidence, scale_used

        elif engine_preference.lower() in ["paddle", "paddleocr", "auto"]:
            if not self.paddle_engine.available:
                return "PaddleOCR (unavailable)", "", 0.0, 1.0

            # Smart selection: GPU if available, CPU as fallback
            prefer_gpu = self.paddle_engine.gpu_available
            engine_name = "PaddleOCR (GPU)" if prefer_gpu else "PaddleOCR (CPU)"

            text, confidence, scale_used = self.paddle_engine.recognise_text(
                processed_img,
                whitelist,
                blacklist,
                prefer_gpu=prefer_gpu,
                early_exit_enabled=early_exit_enabled,
                roi_meta=roi_meta,
            )
            return engine_name, text, confidence, scale_used

        else:
            # Unknown engine, fallback to PaddleOCR
            if self.paddle_engine.available:
                prefer_gpu = self.paddle_engine.gpu_available
                engine_name = f"PaddleOCR (GPU fallback)" if prefer_gpu else "PaddleOCR (CPU fallback)"
                text, confidence, scale_used = self.paddle_engine.recognise_text(
                    processed_img, whitelist, blacklist, prefer_gpu=prefer_gpu
                )
                return engine_name, text, confidence, scale_used

            return f"Unknown engine ({engine_preference})", "", 0.0, 1.0

    def _validate_and_score_result(
        self, text: str, confidence: float, roi_meta: ROIMeta, strict_patterns: bool = False
    ) -> Tuple[bool, str, float]:
        # Validate text and calculate unified score
        try:
            rule_passed, rule_message = self.validator.validate_text(roi_meta, text)
            score = self.calculate_unified_score(text, confidence, rule_passed, strict_patterns)
            return rule_passed, rule_message, score
        except Exception as e:
            logging.warning(f"Validation failed for text '{text}': {e}")
            return False, f"Validation error: {e}", confidence

    def _should_early_exit(
        self, text: str, confidence: float, roi_meta: Optional[object], early_exit_enabled: bool
    ) -> bool:  # Check if early exit conditions are met
        if not early_exit_enabled or confidence < OCRConfig.EARLY_EXIT_CONFIDENCE:
            return False

        if roi_meta:
            try:
                rule_passed, _ = self.validator.validate_text(roi_meta, text, debug=False)
                return rule_passed
            except Exception as e:
                logging.debug(f"Early exit validation failed: {e}")

        # Fallback: very high confidence threshold
        return confidence > OCRConfig.FALLBACK_HIGH_CONFIDENCE

    def calculate_unified_score(
        self, text: str, confidence: float, rule_passed: bool, strict_patterns: bool = False
    ) -> float:  # Unified scoring function
        score = 0

        # Pattern match is most important
        if rule_passed:
            score += OCRConfig.PATTERN_MATCH_SCORE
        elif strict_patterns:
            # In strict mode, heavily penalise pattern failures
            score += OCRConfig.PATTERN_FAILURE_PENALTY

        # Confidence percentage (0-100 points)
        score += confidence

        # Non-empty text bonus
        if text.strip():
            score += OCRConfig.NON_EMPTY_BONUS

        # Content completeness bonus (prefer "Phase: 3" over "Phase:")
        meaningful_chars = len([c for c in text if c.isalnum()])
        score += min(meaningful_chars, OCRConfig.MAX_CONTENT_BONUS)

        return score

    def _sort_results_by_unified_score(self, results, roi_meta: ROIMeta = None):  # Sort OCR results by unified score
        def calculate_score(result_tuple):
            engine_name, scaled_display, text, confidence, rule_passed, rule_message = result_tuple
            # Enable strict patterns if ROI has pattern defined
            strict_patterns = roi_meta and hasattr(roi_meta, "pattern") and getattr(roi_meta, "pattern", "").strip()
            return self.calculate_unified_score(text, confidence, rule_passed, strict_patterns)

        results.sort(key=calculate_score, reverse=True)

    def _try_preferred_engine(
        self,
        image: Image.Image,
        roi_meta: ROIMeta,
        preferred_engine: str,
        whitelist: Optional[str],
        blacklist: Optional[str],
        early_exit_enabled: bool,
    ) -> Optional[Tuple[str, Image.Image, str, float, bool, str]]:
        # Try the preferred engine with basic preprocessing
        try:
            # Use simple preprocessing for preferred engine attempt
            candidates = self.preprocessor.create_candidates(image)

            # Try the first preprocessing method (usually original or basic enhancement)
            method_name, processed_img = candidates[0] if candidates else ("original", image)

            # Use centralized engine selection
            engine_display, text, confidence, scale_used = self._select_and_run_engine(
                preferred_engine, processed_img, whitelist, blacklist, early_exit_enabled, roi_meta
            )

            # If engine unavailable, return None
            if "unavailable" in engine_display.lower() or not text:
                return None

            # Create preferred engine name
            engine_name = f"{method_name}-{engine_display}-Preferred"

            # Validate result
            rule_passed, rule_message = self.validator.validate_text(roi_meta, text)
            scaled_display = self._scale_display_image(processed_img, scale_used)

            return (engine_name, scaled_display, text, confidence, rule_passed, rule_message)

        except Exception as e:
            logging.warning(f"Preferred engine '{preferred_engine}' failed: {e}")
            return None

    def _try_preferred_engine_first(
        self,
        image: Image.Image,
        roi_meta: ROIMeta,
        whitelist: Optional[str],
        blacklist: Optional[str],
        early_exit_enabled: bool,
    ) -> List[Tuple[str, Image.Image, str, float, bool, str]]:
        # Try preferred engine first if specified
        results = []
        preferred_engine = getattr(roi_meta, "preferred_ocr_engine", "auto")

        if preferred_engine and preferred_engine != "auto":
            preferred_result = self._try_preferred_engine(
                image, roi_meta, preferred_engine, whitelist, blacklist, early_exit_enabled
            )

            if preferred_result:
                engine_name, processed_img, text, confidence, rule_passed, rule_message = preferred_result
                results.append((engine_name, processed_img, text, confidence, rule_passed, rule_message))

        return results

    def process_multi_engine(  # Process image with all engines and all preprocessing methods
        self,
        image: Image.Image,
        roi_meta: ROIMeta,
        accepted_chars: Optional[str] = None,
        early_exit_enabled: bool = True,
    ) -> List[Tuple[str, Image.Image, str, float, bool, str]]:
        # Process image with all available engines across all preprocessing methods using unified scoring
        # Input validation
        if not image or not roi_meta:
            logging.error("Invalid input: image or roi_meta is None")
            return []

        if not self.available:
            logging.error("No OCR engines available")
            return []

        # Get character filtering settings
        whitelist, blacklist = self._get_filters(roi_meta, accepted_chars)

        # Try preferred engine first
        results = self._try_preferred_engine_first(image, roi_meta, whitelist, blacklist, early_exit_enabled)

        # If preferred engine gives high confidence, use it (early exit)
        if results and results[0][3] >= OCRConfig.EARLY_EXIT_CONFIDENCE:
            return results

        # Create all preprocessing candidates
        candidates = self.preprocessor.create_candidates(image)

        # Track globally best result across all methods for early exit decisions
        global_best_score = 0
        global_best_result = None
        strict_patterns = hasattr(roi_meta, "pattern") and getattr(roi_meta, "pattern", "").strip()

        # Test each preprocessing method with all engines
        for method_name, processed_img in candidates:
            # Test all engines on this preprocessing method
            engine_results = self._test_engines(processed_img, roi_meta, whitelist, blacklist, early_exit_enabled)

            # Add method name to engine results and append to main results
            for engine_name, scaled_display, text, confidence, rule_passed, rule_message in engine_results:
                combined_name = f"{method_name}-{engine_name}"
                results.append((combined_name, scaled_display, text, confidence, rule_passed, rule_message))

                # Track the globally best result using unified scoring
                unified_score = self.calculate_unified_score(text, confidence, rule_passed, strict_patterns)
                if unified_score > global_best_score:
                    global_best_score = unified_score
                    global_best_result = (combined_name, text, confidence, rule_passed, unified_score)

            # Global early exit: if we have an excellent result (high confidence AND pattern match), stop processing
            if early_exit_enabled and global_best_result:
                name, text, confidence, rule_passed, score = global_best_result
                if confidence >= OCRConfig.EARLY_EXIT_CONFIDENCE and rule_passed:
                    # Sort all results before returning to ensure best result is first
                    self._sort_results_by_unified_score(results, roi_meta)
                    return results

        # Sort all results by unified score before returning
        self._sort_results_by_unified_score(results, roi_meta)
        return results


# Global instance for easy access
_processor_instance: Optional[OCRProcessor] = None


def get_ocr_processor() -> OCRProcessor:  # Get the global OCRProcessor singleton instance
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = OCRProcessor()
    return _processor_instance
