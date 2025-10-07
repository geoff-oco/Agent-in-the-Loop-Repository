# Bulk capture manager for efficient screenshot capture across multiple phases
import logging
import time
from typing import Dict, List, Optional
from PIL import Image


class BulkCaptureManager:
    def __init__(self, screen_capture, navigation_controller, progress_reporter=None):
        self.screen_capture = screen_capture
        self.navigation = navigation_controller
        self.progress_reporter = progress_reporter
        self.captured_screenshots = {}  # {phase_num: PIL.Image}
        self.red2_final_screenshots = []  # List of 5 screenshots for animation averaging

    def execute_capture_plan(self, capture_plan: Dict, monitor_index: int, base_unit_rois: Dict = None) -> Dict:
        # Navigate and capture according to plan
        # Returns: {"phase_screenshots": {...}, "red2_final_screenshots": [...] or []}
        # base_unit_rois: Required for red2 final navigation

        phases_to_capture = capture_plan["phases_to_capture"]
        needs_red2_final = capture_plan["needs_red2_final"]

        print("\n=== Bulk Screenshot Capture ===")
        print(f"Phases to capture: {phases_to_capture}")
        print(f"Red2 final needed: {needs_red2_final}")
        print("\nDO NOT MOVE MOUSE during capture phase...")

        # Start from Phase 1
        if 1 in phases_to_capture:
            print("\nNavigating to Phase 1...")
            if self.progress_reporter:
                self.progress_reporter.update("Capturing Phase 1 screenshot...", phase=1, percentage=25)

            if not self.navigation.init_phase_one():
                logging.error("Failed to initialise to Phase 1")
                raise RuntimeError("Failed to navigate to Phase 1")

            # Reset view to ensure consistent camera
            self.navigation.click_resetview()
            time.sleep(0.3)  # Brief delay for view to settle

            # Capture Phase 1
            screenshot = self.screen_capture.capture_monitor(monitor_index)
            if screenshot:
                self.captured_screenshots[1] = screenshot
                print("Phase 1 screenshot captured")
            else:
                logging.error("Failed to capture Phase 1 screenshot")
                raise RuntimeError("Phase 1 capture failed")

        # Phase 2
        if 2 in phases_to_capture:
            print("\nNavigating to Phase 2...")
            if self.progress_reporter:
                self.progress_reporter.update("Capturing Phase 2 screenshot...", phase=2, percentage=45)

            if not self.navigation.click_upphase():
                logging.error("Failed to navigate to Phase 2")
                raise RuntimeError("Failed to navigate to Phase 2")

            # Reset view
            self.navigation.click_resetview()
            time.sleep(0.3)

            # Capture Phase 2
            screenshot = self.screen_capture.capture_monitor(monitor_index)
            if screenshot:
                self.captured_screenshots[2] = screenshot
                print("Phase 2 screenshot captured")
            else:
                logging.error("Failed to capture Phase 2 screenshot")
                raise RuntimeError("Phase 2 capture failed")

        # Phase 3
        if 3 in phases_to_capture:
            print("\nNavigating to Phase 3...")
            if self.progress_reporter:
                self.progress_reporter.update("Capturing Phase 3 screenshot...", phase=3, percentage=65)

            if not self.navigation.click_upphase():
                logging.error("Failed to navigate to Phase 3")
                raise RuntimeError("Failed to navigate to Phase 3")

            # Reset view
            self.navigation.click_resetview()
            time.sleep(0.3)

            # Capture Phase 3
            screenshot = self.screen_capture.capture_monitor(monitor_index)
            if screenshot:
                self.captured_screenshots[3] = screenshot
                print("Phase 3 screenshot captured")
            else:
                logging.error("Failed to capture Phase 3 screenshot")
                raise RuntimeError("Phase 3 capture failed")

        # Red2 final unit count (only if Phase 3 has actions)
        if needs_red2_final:
            print("\nNavigating to Red1 base for Red2 final count...")
            if self.progress_reporter:
                self.progress_reporter.update("Capturing Red2 final unit count (5 frames)...", phase=3, percentage=75)

            if not base_unit_rois or not self.navigation.navigate_to_red1_base(
                monitor_index, base_unit_rois, dry_run=False
            ):
                logging.warning("Failed to navigate to Red1 for Red2 final count")
                # Non-critical, continue without it
            else:
                # Capture 5 screenshots at 0.2s intervals for animation averaging
                print("Capturing 5 frames for Red2 final count (animation averaging)...")
                for i in range(5):
                    screenshot = self.screen_capture.capture_monitor(monitor_index)
                    if screenshot:
                        self.red2_final_screenshots.append(screenshot)
                        print(f"  Frame {i+1}/5 captured")
                    else:
                        logging.warning(f"Failed to capture Red2 final screenshot frame {i+1}")

                    # Wait 0.75s between captures (except after last one) for animation averaging
                    if i < 4:
                        time.sleep(0.75)

                print(f"Red2 final count capture complete ({len(self.red2_final_screenshots)} frames)")

                # Reset view after Red2 final captures to return to neutral state
                print("Resetting view...")
                self.navigation.click_resetview()
                time.sleep(0.2)  # Brief delay for view reset to complete

        print("\nAll captures complete - you can now move your mouse!")
        if self.progress_reporter:
            self.progress_reporter.update("Screenshots captured, processing OCR...", percentage=80)

        return {"phase_screenshots": self.captured_screenshots, "red2_final_screenshots": self.red2_final_screenshots}
