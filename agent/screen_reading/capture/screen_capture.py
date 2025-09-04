"""Screen capture functionality using MSS for fast window and monitor capture."""

import os
import time
import logging
from typing import Optional, Tuple

import numpy as np
import mss
import cv2
from dotenv import load_dotenv

from .window_detector import WindowDetector, Rect

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Fast screen and window capture using MSS."""

    def __init__(self, monitor_index: int = None, prefer_window: bool = True):
        self.monitor_index = monitor_index or int(os.getenv("DEFAULT_MONITOR", "1"))
        self.prefer_window = prefer_window
        self.window_detector = WindowDetector()

        logger.info(f"ScreenCapture initialized: monitor={self.monitor_index}, prefer_window={prefer_window}")

    def capture_target(self) -> Tuple[Optional[Rect], Optional[np.ndarray]]:
        """Capture target screen area with window/monitor fallback."""
        try:
            # Try window capture first if preferred
            if self.prefer_window:
                window_bounds = self.window_detector.find_target_window()
                if window_bounds and self.window_detector.is_window_valid(window_bounds):
                    try:
                        image = self.capture_window(window_bounds)
                        logger.info(f"Successfully captured window: {window_bounds}")
                        return window_bounds, image
                    except Exception as e:
                        logger.warning(f"Window capture failed, falling back to monitor: {e}")

            # Fallback to monitor capture
            image = self.capture_monitor()
            if image is not None:
                # Use full monitor bounds as placeholder
                monitor_bounds = (0, 0, image.shape[1], image.shape[0])
                logger.info(f"Successfully captured monitor {self.monitor_index}")
                return monitor_bounds, image

            logger.error("Both window and monitor capture failed")
            return None, None

        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None, None

    def capture_window(self, window_bounds: Rect) -> np.ndarray:
        """Capture specific window region as BGR array."""
        if not self.window_detector.is_window_valid(window_bounds):
            raise ValueError(f"Invalid window bounds: {window_bounds}")

        try:
            left, top, width, height = window_bounds

            with mss.mss() as sct:
                # MSS expects a monitor-like dictionary
                monitor = {"left": left, "top": top, "width": width, "height": height}
                screenshot = np.array(sct.grab(monitor))  # Returns RGBA format

                # Convert from RGBA to BGR for OpenCV compatibility
                bgr_image = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

                logger.debug(f"Captured window region: {bgr_image.shape[1]}x{bgr_image.shape[0]}")
                return bgr_image

        except Exception as e:
            logger.error(f"Window capture failed for bounds {window_bounds}: {e}")
            raise

    def capture_monitor(self) -> np.ndarray:
        """Capture full monitor as BGR array."""
        try:
            with mss.mss() as sct:
                monitors = sct.monitors

                # Validate and clamp monitor index
                if self.monitor_index >= len(monitors) or self.monitor_index <= 0:
                    logger.warning(f"Monitor {self.monitor_index} invalid, using primary monitor")
                    monitor_index = 1
                else:
                    monitor_index = self.monitor_index

                monitor = monitors[monitor_index]
                logger.debug(f"Capturing monitor {monitor_index}: {monitor}")

                screenshot = np.array(sct.grab(monitor))  # Returns RGBA format
                bgr_image = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

                logger.debug(f"Captured screen: {bgr_image.shape[1]}x{bgr_image.shape[0]}")
                return bgr_image

        except Exception as e:
            logger.error(f"Monitor capture failed: {e}")
            raise

    def save_debug_capture(self, image: np.ndarray, filename: str, roi_name: str = None) -> None:
        """Save image to debug directory."""
        try:
            debug_dir = "roi_captures"
            os.makedirs(debug_dir, exist_ok=True)

            # Build filename with timestamp
            timestamp = int(time.time())
            debug_filename = f"{timestamp}_{filename}"

            if roi_name:
                name_part, ext = os.path.splitext(debug_filename)
                debug_filename = f"{name_part}_{roi_name}{ext}"

            # Add .png extension if not present
            if not debug_filename.endswith(".png"):
                debug_filename += ".png"

            debug_path = os.path.join(debug_dir, debug_filename)
            success = cv2.imwrite(debug_path, image)

            if success:
                logger.debug(f"Saved debug image: {debug_path}")
            else:
                logger.warning(f"Failed to save debug image: {debug_path}")

        except Exception as e:
            logger.warning(f"Failed to save debug image '{filename}': {e}")
