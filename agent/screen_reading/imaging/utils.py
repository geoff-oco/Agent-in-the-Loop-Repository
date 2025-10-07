# Image utility functions for ROI cropping and scaling
from typing import Optional
from PIL import Image
from core.models import ROIMeta


class ImageUtils:  # Utilities for image manipulation and ROI processing

    @staticmethod
    def crop_roi(  # Crop image to ROI boundaries with intelligent padding.
        image: Image.Image, roi_meta: ROIMeta, padding_pixels: Optional[int] = None
    ) -> Optional[Image.Image]:
        if not image:
            return None

        # Calculate absolute pixel coordinates from relative values
        x = int(roi_meta.x * image.width)
        y = int(roi_meta.y * image.height)
        w = max(1, int(roi_meta.w * image.width))
        h = max(1, int(roi_meta.h * image.height))

        # Determine padding - prioritise parameter, then ROI setting, then default
        if padding_pixels is not None:
            padding = padding_pixels
        else:
            padding = getattr(roi_meta, "padding_pixels", 10)

        # Ensure minimum padding for OCR accuracy
        padding = max(padding, 5)  # Never go below 5px for OCR context

        # Apply symmetric padding within image bounds
        x0 = max(0, x - padding)
        y0 = max(0, y - padding)
        x1 = min(image.width, x + w + padding)
        y1 = min(image.height, y + h + padding)

        return image.crop((x0, y0, x1, y1))
