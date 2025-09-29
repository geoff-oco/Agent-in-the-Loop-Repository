# Screen capture functionality using MSS
from typing import List, Optional, Tuple, Dict
from PIL import Image
import time

# Import MSS with fallback handling
try:
    import mss

    _mss_available = True
except ImportError:
    mss = None
    _mss_available = False


class ScreenCapture:  # Handles screen capture using MSS library.
    # Supports multiple monitor detection and efficient frame capture.

    def __init__(self):
        self._sct_instance = None
        self._monitors_cache = []
        self._cache_time = 0
        self._cache_duration = 5.0  # Cache monitors for 5 seconds

    @property
    def available(self) -> bool:  # Check if MSS screen capture is available
        return _mss_available

    def get_monitors(
        self, refresh_cache: bool = False
    ) -> List[Dict]:  # Get list of available monitors with dimensions.
        current_time = time.time()

        # Use cached monitors if available and recent
        if not refresh_cache and self._monitors_cache and current_time - self._cache_time < self._cache_duration:
            return self._monitors_cache

        monitors = []
        if not self.available:
            # Fallback when MSS unavailable
            monitors = [
                {
                    "index": 1,
                    "width": 1920,
                    "height": 1080,
                    "description": "Monitor 1 (1920x1080) - Fallback",
                }
            ]
        else:
            try:
                with mss.mss() as sct:
                    for i in range(1, len(sct.monitors)):  # Skip index 0 (all monitors)
                        mon = sct.monitors[i]
                        monitors.append(
                            {
                                "index": i,
                                "width": mon["width"],
                                "height": mon["height"],
                                "description": f"Monitor {i} ({mon['width']}x{mon['height']})",
                            }
                        )
            except Exception:
                # Fallback on error
                monitors = [
                    {
                        "index": 1,
                        "width": 1920,
                        "height": 1080,
                        "description": "Monitor 1 (1920x1080) - Default",
                    }
                ]

        # Update cache
        self._monitors_cache = monitors
        self._cache_time = current_time
        return monitors

    def capture_monitor(
        self, monitor_index: int = 1
    ) -> Optional[Image.Image]:  # Capture screenshot from specific monitor.
        if not self.available:
            return None

        try:
            with mss.mss() as sct:
                # Validate monitor index
                if monitor_index < 1 or monitor_index >= len(sct.monitors):
                    monitor_index = 1

                monitor = sct.monitors[monitor_index]
                screenshot = sct.grab(monitor)

                # Convert MSS image to PIL Image
                image = Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)
                return image

        except Exception:
            return None


    def get_monitor_info(
        self, monitor_index: int
    ) -> Optional[Dict]:  # Get dimensions and properties about specific monitor.
        monitors = self.get_monitors()
        for monitor in monitors:
            if monitor["index"] == monitor_index:
                return monitor
        return None


# Global instance for convenience
_capture_instance: Optional[ScreenCapture] = None


def get_screen_capture() -> ScreenCapture:  # Get the global ScreenCapture singleton instance
    global _capture_instance
    if _capture_instance is None:
        _capture_instance = ScreenCapture()
    return _capture_instance
