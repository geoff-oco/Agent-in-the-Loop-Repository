"""Window detection utility for finding target application windows."""

import logging
from typing import List, Optional, Tuple

# Type definition for window bounds
Rect = Tuple[int, int, int, int]  # x, y, width, height

logger = logging.getLogger(__name__)

# Optional window detection - gracefully handle missing dependency
try:
    import pygetwindow as gw

    _CAN_GET_WINDOWS = True
except ImportError:
    _CAN_GET_WINDOWS = False
    logger.warning("pygetwindow not available - window detection disabled")


class WindowDetector:
    """Window detection for target applications."""

    def __init__(self, target_titles: List[str] = None):
        self.target_titles = target_titles or ["RTSViewer", "RTS", "Viewer", "Game"]
        self.can_detect_windows = _CAN_GET_WINDOWS

        if not self.can_detect_windows:
            logger.warning("Window detection unavailable - pygetwindow not installed")

    def find_target_window(self) -> Optional[Rect]:
        """Find target window and return bounds."""
        if not self.can_detect_windows:
            logger.warning("Window detection not available")
            return None

        try:
            for title in self.target_titles:
                windows = gw.getWindowsWithTitle(title)
                if windows and not windows[0].isMinimized:
                    window = windows[0]
                    bounds = (window.left, window.top, window.width, window.height)
                    logger.info(f"Found target window '{title}': {bounds}")
                    return bounds

            logger.warning(f"No target windows found. Searched for: {self.target_titles}")
            return None

        except Exception as e:
            logger.error(f"Window detection failed: {e}")
            return None

    def list_available_windows(self) -> List[str]:
        """List visible window titles for debugging."""
        if not self.can_detect_windows:
            return []

        try:
            windows = gw.getAllWindows()
            titles = [
                f"{w.title} ({w.width}x{w.height})" for w in windows if w.title and not w.isMinimized and w.visible
            ]
            return sorted(titles)
        except Exception as e:
            logger.error(f"Failed to list windows: {e}")
            return []

    def is_window_valid(self, window_bounds: Rect) -> bool:
        """Validate window bounds for screen capture."""
        if not window_bounds or len(window_bounds) != 4:
            return False

        left, top, width, height = window_bounds

        if width <= 0 or height <= 0:
            logger.warning(f"Invalid window dimensions: {width}x{height}")
            return False

        if width < 100 or height < 100:
            logger.warning(f"Window too small: {width}x{height}")
            return False

        if left < -width or top < -height:
            logger.warning(f"Window position appears invalid: ({left}, {top})")
            return False

        return True

    def get_window_info(self, window_bounds: Rect) -> str:
        """Generate window information string."""
        if not self.is_window_valid(window_bounds):
            return "Invalid window bounds"

        left, top, width, height = window_bounds
        return f"Window at ({left}, {top}) size {width}x{height}"
