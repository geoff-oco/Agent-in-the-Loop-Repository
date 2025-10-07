# Image preprocessing methods for OCR optimisation
from typing import List, Tuple, Optional
from PIL import Image
from core.models import ProcessingMethod

# Import CV2 and numpy with fallback handling
try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None


class ImagePreprocessor:  # Handles CV2-based image preprocessing for OCR optimisation

    def __init__(self):
        self.methods_available = cv2 is not None and np is not None

    def create_candidates(
        self, image: Image.Image
    ) -> List[Tuple[str, Image.Image]]:  # Create all preprocessing candidates for multi-candidate OCR.
        candidates = []

        # Always include original image first
        candidates.append(("Original", image))

        if not self.methods_available:
            # Fallback when OpenCV unavailable
            return candidates

        # Convert PIL to OpenCV format for processing
        img_array = np.array(image.convert("RGB"))
        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # Generate all processed candidates
        candidates.append(("Enhanced", self._enhanced_contrast(img_cv)))
        candidates.append(("Binary", self._binary_otsu(img_cv)))
        candidates.append(("Grey-Boost", self._grey_boost_adaptive(img_cv)))
        candidates.append(("Inverted", self._inverted_processing(img_cv)))

        return candidates

    def process_single(  # Process image with specific method - optimised for runtime use.
        self, image: Image.Image, method: ProcessingMethod
    ) -> Image.Image:
        if method == ProcessingMethod.ORIGINAL:
            return image

        if not self.methods_available:
            # Fallback to original when OpenCV unavailable
            return image

        # Convert to OpenCV format
        img_array = np.array(image.convert("RGB"))
        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # Apply specific method
        if method == ProcessingMethod.ENHANCED:
            return self._enhanced_contrast(img_cv)
        elif method == ProcessingMethod.BINARY:
            return self._binary_otsu(img_cv)
        elif method == ProcessingMethod.GREY_BOOST:
            return self._grey_boost_adaptive(img_cv)
        elif method == ProcessingMethod.INVERTED:
            return self._inverted_processing(img_cv)
        else:
            return image

    def _enhanced_contrast(self, img_cv) -> Image.Image:  # Enhanced contrast processing - good for normal/faded text
        enhanced = cv2.convertScaleAbs(img_cv, alpha=1.3, beta=20)
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.medianBlur(enhanced, 3)
        return Image.fromarray(enhanced)

    def _binary_otsu(self, img_cv) -> Image.Image:  # High-contrast binary processing - good for clear black/white text
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 3)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return Image.fromarray(binary)

    def _grey_boost_adaptive(
        self, img_cv
    ) -> Image.Image:  # Grey-boosted adaptive processing - specifically for greyed-out text
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        # Boost grey values to make faded text more prominent
        boosted = cv2.convertScaleAbs(gray, alpha=1.8, beta=30)
        # Apply adaptive thresholding for varying lighting
        adaptive = cv2.adaptiveThreshold(boosted, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        adaptive = cv2.medianBlur(adaptive, 3)
        return Image.fromarray(adaptive)

    def _inverted_processing(self, img_cv) -> Image.Image:  # Inverted processing - for white text on dark backgrounds
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        inverted = cv2.bitwise_not(gray)

        # Apply slight denoising before thresholding
        inverted = cv2.medianBlur(inverted, 3)

        # Use adaptive thresholding for better edge preservation
        inverted_thresh = cv2.adaptiveThreshold(inverted, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 4)

        # Morphological operations to connect broken letter parts
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        # Close small gaps in text
        inverted_closed = cv2.morphologyEx(inverted_thresh, cv2.MORPH_CLOSE, kernel)
        # Light dilation to strengthen text
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (1, 1))
        inverted_final = cv2.dilate(inverted_closed, kernel_dilate, iterations=1)

        return Image.fromarray(inverted_final)
