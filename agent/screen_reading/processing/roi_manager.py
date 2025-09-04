"""Region of Interest (ROI) management for screen capture and image processing."""

import json
import os
import logging
from typing import Dict, Tuple, Optional

import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Type definitions for clarity
Rect = Tuple[int, int, int, int]  # x, y, width, height (absolute pixels)
ROI = Tuple[float, float, float, float]  # x, y, width, height (relative 0.0-1.0)


class ROIManager:
    """ROI management for coordinate conversion and image cropping."""

    def __init__(self, roi_config_path: str = None):
        if roi_config_path is None:
            roi_config_path = os.path.join("config", "rois.json")

        self.roi_config_path = roi_config_path
        self.loaded_rois = {}

        logger.debug(f"ROIManager initialized with config path: {roi_config_path}")

    def load_rois(self, config_path: str = None) -> Dict[str, ROI]:
        """Load ROI definitions from JSON file."""
        config_path = config_path or self.roi_config_path

        try:
            if not os.path.isabs(config_path):
                module_dir = os.path.dirname(os.path.dirname(__file__))
                config_path = os.path.join(module_dir, config_path)

            with open(config_path, "r", encoding="utf-8") as f:
                rois_data = json.load(f)

            logger.info(f"Loading ROI definitions from {config_path}")

            rois = {}
            for name, roi_list in rois_data.items():
                if not isinstance(roi_list, list) or len(roi_list) != 4:
                    logger.warning(
                        f"Invalid ROI '{name}': expected 4 values, got {len(roi_list) if isinstance(roi_list, list) else 'non-list'}"
                    )
                    continue

                roi = tuple(roi_list)
                if not self.validate_roi_bounds(roi):
                    logger.warning(f"Invalid ROI bounds for '{name}': {roi}")
                    continue

                rois[name] = roi

            self.loaded_rois = rois
            logger.info(f"Loaded {len(rois)} valid ROI definitions")
            return rois

        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load ROI file {config_path}: {e}")
            raise

    def crop_roi_relative(self, img: np.ndarray, roi: ROI) -> np.ndarray:
        """Crop image using relative coordinates."""
        if not self.validate_roi_bounds(roi):
            logger.warning(f"Invalid ROI bounds: {roi}")
            return self._create_fallback_image()

        height, width = img.shape[:2]
        x, y, w, h = self._rel_to_abs(roi, width, height)

        cropped = img[y : y + h, x : x + w].copy()

        if cropped.size == 0:
            logger.warning(f"Empty crop for ROI {roi} on image {width}x{height}")
            return self._create_fallback_image()

        return cropped

    def crop_roi_absolute(self, img: np.ndarray, rect: Rect) -> np.ndarray:
        """Crop image using absolute pixel coordinates."""
        x, y, w, h = rect
        height, width = img.shape[:2]

        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = max(1, min(w, width - x))
        h = max(1, min(h, height - y))

        return img[y : y + h, x : x + w].copy()

    def convert_rois_to_absolute(self, rois: Dict[str, ROI], img_shape: Tuple[int, int]) -> Dict[str, Rect]:
        """Convert relative ROIs to absolute pixel coordinates."""
        height, width = img_shape
        rois_abs = {}

        for name, roi_rel in rois.items():
            try:
                rois_abs[name] = self._rel_to_abs(roi_rel, width, height)
                logger.debug(f"ROI {name}: {roi_rel} -> {rois_abs[name]}")
            except Exception as e:
                logger.warning(f"Failed to convert ROI {name}: {e}")

        return rois_abs

    def validate_roi_bounds(self, roi: ROI) -> bool:
        """Validate ROI coordinates are within bounds."""
        if not roi or len(roi) != 4:
            return False

        x, y, w, h = roi

        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return False

        if not (0.0 < w <= 1.0 and 0.0 < h <= 1.0):
            return False

        if x + w > 1.0 or y + h > 1.0:
            return False

        return True

    def get_roi_info(self, roi_name: str) -> Optional[Dict]:
        if roi_name not in self.loaded_rois:
            return None

        roi = self.loaded_rois[roi_name]
        return {
            "name": roi_name,
            "coordinates": roi,
            "x_rel": roi[0],
            "y_rel": roi[1],
            "width_rel": roi[2],
            "height_rel": roi[3],
            "area_fraction": roi[2] * roi[3],
        }

    def list_available_rois(self) -> Dict[str, ROI]:
        return self.loaded_rois.copy()

    def _rel_to_abs(self, roi_rel: ROI, width: int, height: int) -> Rect:
        x_rel, y_rel, w_rel, h_rel = roi_rel

        x_abs = max(0, min(int(x_rel * width), width - 1))
        y_abs = max(0, min(int(y_rel * height), height - 1))
        w_abs = max(1, min(int(w_rel * width), width - x_abs))
        h_abs = max(1, min(int(h_rel * height), height - y_abs))

        return (x_abs, y_abs, w_abs, h_abs)

    def _create_fallback_image(self) -> np.ndarray:
        return np.zeros((10, 10, 3), dtype=np.uint8)

    def save_rois(self, rois: Dict[str, ROI], output_path: str = None) -> bool:
        """Save ROI definitions to JSON file."""
        output_path = output_path or self.roi_config_path

        try:
            rois_data = {name: list(roi) for name, roi in rois.items()}

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(rois_data, f, indent=2)

            logger.info(f"Saved {len(rois)} ROI definitions to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save ROIs to {output_path}: {e}")
            return False

    def create_roi(self, name: str, x: float, y: float, width: float, height: float) -> bool:
        """Create and add new ROI definition."""
        roi = (x, y, width, height)

        if not self.validate_roi_bounds(roi):
            logger.error(f"Invalid ROI bounds for '{name}': {roi}")
            return False

        self.loaded_rois[name] = roi
        logger.info(f"Created ROI '{name}': {roi}")
        return True
