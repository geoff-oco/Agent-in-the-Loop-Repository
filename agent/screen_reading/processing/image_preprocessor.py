"""Image preprocessing for OCR optimization using OpenCV operations."""

import logging
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Image preprocessing for OCR optimization."""

    def __init__(
        self,
        scale_factor: float = 2.0,
        enhance_contrast: bool = True,
        invert_colors: bool = True,
        apply_morphology: bool = True,
    ):
        self.scale_factor = scale_factor
        self.enhance_contrast = enhance_contrast
        self.invert_colors = invert_colors
        self.apply_morphology = apply_morphology

        logger.debug(
            f"ImagePreprocessor initialized: scale={scale_factor}, enhance={enhance_contrast}, "
            f"invert={invert_colors}, morph={apply_morphology}"
        )

    def preprocess_for_ocr(self, img: np.ndarray) -> np.ndarray:
        """Apply preprocessing pipeline for OCR optimization."""
        try:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()

            if self.scale_factor > 1.0:
                gray = self._scale_image(gray, self.scale_factor)

            denoised = self._apply_denoising(gray)

            if self.enhance_contrast:
                denoised = self._enhance_contrast(denoised)

            if self.invert_colors and self._should_invert(gray):
                denoised = cv2.bitwise_not(denoised)

            binary = self._apply_threshold(denoised)

            if self.apply_morphology:
                binary = self._apply_morphological_cleanup(binary)

            return binary

        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    def preprocess_for_template_matching(self, img: np.ndarray) -> np.ndarray:
        """Apply light preprocessing for template matching."""
        try:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()

            denoised = cv2.medianBlur(gray, 3)

            return denoised

        except Exception as e:
            logger.error(f"Template matching preprocessing failed: {e}")
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    def _scale_image(self, img: np.ndarray, scale_factor: float) -> np.ndarray:
        height, width = img.shape
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        return cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

    def _apply_denoising(self, img: np.ndarray) -> np.ndarray:
        return cv2.medianBlur(img, 3)

    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        return clahe.apply(img)

    def _should_invert(self, img: np.ndarray) -> bool:
        return np.mean(img) < 127

    def _apply_threshold(self, img: np.ndarray) -> np.ndarray:
        _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def _apply_morphological_cleanup(self, img: np.ndarray) -> np.ndarray:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))

        cleaned = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)

        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

        return cleaned

    def create_custom_preprocessor(self, **kwargs):
        config = {
            "scale_factor": self.scale_factor,
            "enhance_contrast": self.enhance_contrast,
            "invert_colors": self.invert_colors,
            "apply_morphology": self.apply_morphology,
        }
        config.update(kwargs)
        return ImagePreprocessor(**config)
