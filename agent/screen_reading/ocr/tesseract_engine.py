# Pytesseract OCR engine optimised for single character and text recognition with enhanced scaling
from typing import Tuple, Optional, Dict, List
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pytesseract
import re
import time
import os


class TesseractEngine:
    # Pytesseract-based OCR engine optimised for single characters and general text

    def __init__(self):
        # Initialise Tesseract with availability check
        self.available = self._check_tesseract_availability()

        # PSM (Page Segmentation Mode) options for different text types
        self.psm_modes = {
            "single_char": 10,  # Single character (best for phase numbers)
            "single_word": 8,  # Single word
            "single_line": 7,  # Single line
            "single_column": 4,  # Single column of text
            "single_block": 6,  # Single uniform block of text
            "auto": 3,  # Automatic (fallback)
        }

    def _check_tesseract_availability(self) -> bool:
        # Check if Tesseract is available on the system
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            print("Warning: Tesseract not available. Install tesseract-ocr to enable.")
            return False

    def recognise_text(
        self,
        image: Image.Image,
        whitelist: Optional[str] = None,
        blacklist: Optional[str] = None,
        early_exit_enabled: bool = False,
        roi_meta: Optional[object] = None,
    ) -> Tuple[str, float, float]:
        # Recognise text using multi-scale testing with appropriate PSM mode selection
        if not self.available:
            return "", 0.0, 1.0

        start_time = time.time()

        # Initialize validator for early exit if enabled
        validator = None
        if early_exit_enabled and roi_meta:
            try:
                from core.validators import get_text_validator

                validator = get_text_validator()
            except ImportError:
                pass  # Validator not available, disable early exit

        # Determine if this is likely single character or multi-character text
        is_single_char = self._is_single_character_context(image, whitelist)

        # Generate test scales based on content type
        test_scales = self._generate_optimal_scales(image, is_single_char)

        # Select appropriate methods based on context
        if is_single_char:
            methods = [
                ("single_char_scaled_inverted", self._single_char_scaled_inverted),
                ("single_char_enhanced", self._single_char_enhanced),
                ("single_word_scaled", self._single_word_scaled),
            ]
        else:
            methods = [
                ("multi_char_enhanced", self._multi_char_enhanced),
                ("single_word_scaled", self._single_word_scaled),
                ("single_line_optimised", self._single_line_optimised),
            ]

        best_result = ("", 0.0)
        best_confidence = 0.0
        best_scale = 1.0

        # Test each scale with each method
        for scale in test_scales:
            # Scale image if needed
            if abs(scale - 1.0) > 0.01:
                new_width = int(image.width * scale)
                new_height = int(image.height * scale)
                scaled_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            else:
                scaled_image = image

            for method_name, method_func in methods:
                try:
                    # Use the method with the scaled image (methods handle their own preprocessing)
                    text, confidence = method_func(scaled_image, whitelist, blacklist)

                    if confidence > best_confidence and text.strip():
                        best_result = (text, confidence)
                        best_confidence = confidence
                        best_scale = scale

                        # Early exit if confidence > 92% AND pattern validates (when enabled)
                        if early_exit_enabled and validator and confidence > 92.0:
                            rule_passed, _ = validator.validate_text(roi_meta, text, debug=False)
                            if rule_passed:
                                # Break from both loops (processor will handle debug output)
                                break

                        # Fallback early exit for very high confidence
                        if confidence > 90.0:
                            break
                except Exception as e:
                    continue  # Try next method

            # Early exit if we got very high confidence (like original)
            if best_confidence > 90.0:
                break
            # Check if early exit was triggered (confidence > 92% + pattern match)
            if early_exit_enabled and validator and best_confidence > 92.0 and best_result[0]:
                rule_passed, _ = validator.validate_text(roi_meta, best_result[0], debug=False)
                if rule_passed:
                    break

        if best_result[0]:
            return best_result[0], best_result[1], best_scale
        else:
            return "(empty)", 0.0, 1.0

    def _generate_optimal_scales(self, image: Image.Image, is_single_char: bool) -> List[float]:
        # Generate test scales optimised for Tesseract (1x-3x range)
        # Configurable via OCR_MAX_SCALES env var (default: 5 for accuracy, 3 for speed)
        if is_single_char:
            # Single characters need more aggressive scaling (2x-3x range)
            scales = [3.0, 2.5, 2.0, 1.5, 1.0]
        else:
            # Multi-character text works better with moderate scaling (1x-2x range)
            scales = [2.0, 1.5, 1.0, 2.5, 1.2]

        # Filter out unreasonable scales based on image size
        filtered_scales = []
        for scale in scales:
            scaled_width = image.width * scale
            scaled_height = image.height * scale
            # Avoid extremely large images that would be slow
            if scaled_width <= 1000 and scaled_height <= 1000:
                filtered_scales.append(scale)

        # Limit scales if configured (for performance on lower-end systems)
        max_scales = int(os.getenv("OCR_MAX_SCALES", "5"))
        if len(filtered_scales) > max_scales:
            filtered_scales = filtered_scales[:max_scales]

        return filtered_scales if filtered_scales else [1.0]

    def _is_single_character_context(self, image: Image.Image, whitelist: Optional[str]) -> bool:
        # Determine if the image likely contains a single character        # Check whitelist for single character hints
        if whitelist and len(whitelist) <= 3:
            return True

        # Check image aspect ratio and size
        if image.width < 30 and image.height < 30:
            return True

        aspect_ratio = image.width / image.height if image.height > 0 else 1
        if 0.7 <= aspect_ratio <= 1.3:  # Roughly square, likely single char
            return True

        return False

    def _single_char_scaled_inverted(
        self, image: Image.Image, whitelist: Optional[str], blacklist: Optional[str] = None
    ) -> Tuple[str, float]:
        # Best method for single characters: invert colours (scaling done externally)        # Invert colours (white text to black text on white background)
        inverted_image = ImageOps.invert(image.convert("RGB"))

        # Use single character PSM mode
        config = f'--psm {self.psm_modes["single_char"]}'
        if whitelist:
            config += f" -c tessedit_char_whitelist={whitelist}"

        return self._perform_ocr(inverted_image, config, whitelist, blacklist)

    def _single_char_enhanced(
        self, image: Image.Image, whitelist: Optional[str], blacklist: Optional[str] = None
    ) -> Tuple[str, float]:
        # Enhanced contrast single character recognition (scaling done externally)        # Enhance contrast
        enhanced_image = ImageEnhance.Contrast(image).enhance(2.5)

        # Use single character PSM mode
        config = f'--psm {self.psm_modes["single_char"]}'
        if whitelist:
            config += f" -c tessedit_char_whitelist={whitelist}"

        return self._perform_ocr(enhanced_image, config, whitelist, blacklist)

    def _single_word_scaled(
        self, image: Image.Image, whitelist: Optional[str], blacklist: Optional[str] = None
    ) -> Tuple[str, float]:
        # Single word mode (scaling done externally)        # Use single word PSM mode
        config = f'--psm {self.psm_modes["single_word"]}'
        if whitelist:
            config += f" -c tessedit_char_whitelist={whitelist}"

        return self._perform_ocr(image, config, whitelist, blacklist)

    def _multi_char_enhanced(
        self, image: Image.Image, whitelist: Optional[str], blacklist: Optional[str] = None
    ) -> Tuple[str, float]:
        # Enhanced method for multi-character text (scaling done externally)        # Apply sharpening filter for better edges
        sharpened = image.filter(ImageFilter.SHARPEN)

        # Enhance contrast
        enhanced = ImageEnhance.Contrast(sharpened).enhance(1.5)

        # Use single line PSM mode for multi-char text
        config = f'--psm {self.psm_modes["single_line"]}'
        if whitelist:
            config += f" -c tessedit_char_whitelist={whitelist}"

        return self._perform_ocr(enhanced, config, whitelist, blacklist)

    def _single_line_optimised(
        self, image: Image.Image, whitelist: Optional[str], scale: float = 2.0, blacklist: Optional[str] = None
    ) -> Tuple[str, float]:
        # Optimised method for single line text        # Scale with provided factor
        scaled_image = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)

        # Convert to greyscale if not already
        if scaled_image.mode != "L":
            scaled_image = scaled_image.convert("L")

        # Apply bilateral-like smoothing (edge-preserving)
        smoothed = scaled_image.filter(ImageFilter.MedianFilter(size=3))

        # Use single line PSM mode
        config = f'--psm {self.psm_modes["single_line"]}'
        if whitelist:
            config += f" -c tessedit_char_whitelist={whitelist}"

        return self._perform_ocr(smoothed, config, whitelist, blacklist)

    def _auto_fallback(
        self, image: Image.Image, whitelist: Optional[str], blacklist: Optional[str] = None
    ) -> Tuple[str, float]:
        # Automatic mode fallback with adaptive scaling        # Adaptive scaling based on image size
        if image.height < 20:
            scale = 3.0
        elif image.height < 40:
            scale = 2.0
        else:
            scale = 1.5

        scaled_image = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)

        # Use auto PSM mode
        config = f'--psm {self.psm_modes["auto"]}'
        if whitelist:
            config += f" -c tessedit_char_whitelist={whitelist}"

        return self._perform_ocr(scaled_image, config, whitelist, blacklist)

    def _perform_ocr(
        self, image: Image.Image, config: str, whitelist: Optional[str] = None, blacklist: Optional[str] = None
    ) -> Tuple[str, float]:
        # Perform OCR with confidence scoring
        try:
            # Get detailed OCR data including confidence
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)

            # Extract text and confidence
            text_parts = []
            confidences = []

            for i, conf in enumerate(data["conf"]):
                if conf > 0:  # Only include confident results
                    word = data["text"][i].strip()
                    if word:  # Only include non-empty words
                        text_parts.append(word)
                        confidences.append(conf)

            if not text_parts:
                return "", 0.0

            # Combine text and calculate average confidence
            text = "".join(text_parts)  # No spaces for single characters
            avg_confidence = sum(confidences) / len(confidences)

            # Clean up text - apply character filtering
            if whitelist:
                # Only keep characters that are in the whitelist
                text = "".join(char for char in text if char in whitelist)
            elif blacklist:
                # Remove characters that are in the blacklist
                text = "".join(char for char in text if char not in blacklist)
            else:
                # Default: remove non-alphanumeric characters
                text = re.sub(r"[^0-9a-zA-Z]", "", text)

            return text, avg_confidence

        except Exception as e:
            print(f"OCR processing failed: {e}")
            return "", 0.0

    def recognise_single_character(self, image: Image.Image, whitelist: str = "123") -> Tuple[str, float, float]:
        # Specialised method for single character recognition (optimised for phase numbers)
        if not self.available:
            return "", 0.0, 1.0

        # Use the most effective method for single characters
        text, confidence = self._single_char_scaled_inverted(image, whitelist, None)
        return text, confidence, 1.0  # Single character methods don't use multi-scale testing

    def recognise_with_optimal_scale(
        self, image: Image.Image, scale: float, whitelist: Optional[str] = None
    ) -> Tuple[str, float, float]:
        # Recognise text using a pre-calculated optimal scale
        if not self.available:
            return "", 0.0, scale

        # Scale the image
        scaled_image = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)

        # Determine best PSM mode based on scaled image size
        if scaled_image.width < 50 and scaled_image.height < 50:
            psm = self.psm_modes["single_char"]
        elif scaled_image.width < 200:
            psm = self.psm_modes["single_word"]
        else:
            psm = self.psm_modes["single_line"]

        config = f"--psm {psm}"
        if whitelist:
            config += f" -c tessedit_char_whitelist={whitelist}"

        text, confidence = self._perform_ocr(scaled_image, config, whitelist, None)
        return text, confidence, scale


# Global instance management
_tesseract_instance: Optional[TesseractEngine] = None


def get_tesseract_engine() -> TesseractEngine:
    # Get the global TesseractEngine singleton instance
    global _tesseract_instance
    if _tesseract_instance is None:
        _tesseract_instance = TesseractEngine()
    return _tesseract_instance
