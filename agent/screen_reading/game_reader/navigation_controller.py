# Game navigation and automation controller
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import pyautogui

from core.models import ROIMeta
from imaging.utils import ImageUtils


class NavigationController:  # Handles game navigation and special capture sequences

    def __init__(
        self,
        screen_capture,
        ocr_processor,
        output_manager,
        dry_run: bool = False,
        fast_mode: bool = True,
    ):
        self.screen_capture = screen_capture
        self.ocr_processor = ocr_processor
        self.output_manager = output_manager
        self.dry_run = dry_run

        # Navigation state
        self.current_phase: int = 1

        # Delay configuration (fast_mode reduces delays for speed)
        self.delay_multiplier = 0.2 if fast_mode else 1.0

        # ROI-based button clicking (set after ROIs are loaded)
        self.button_rois: Optional[Dict[str, ROIMeta]] = None
        self.monitor_index: Optional[int] = None

        # Configure PyAutoGUI
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

    def _delay(self, seconds: float):
        # Apply delay adjusted by multiplier for fast/slow mode control
        time.sleep(seconds * self.delay_multiplier)

    def _click_roi_button(self, roi: ROIMeta, button_name: str) -> bool:
        # Click button using ROI coordinates (resolution-independent, multi-monitor aware)
        try:
            if self.monitor_index is None:
                print(f"Error: monitor_index not set, cannot click {button_name}")
                return False

            # Get monitor offset position for multi-monitor support
            import mss

            with mss.mss() as sct:
                if self.monitor_index < 1 or self.monitor_index >= len(sct.monitors):
                    print(f"Error: Invalid monitor_index {self.monitor_index}")
                    return False
                mon = sct.monitors[self.monitor_index]
                mon_left = mon["left"]
                mon_top = mon["top"]
                mon_width = mon["width"]
                mon_height = mon["height"]

            # Convert relative ROI coordinates to absolute screen coordinates
            # Add monitor offset for multi-monitor setups
            click_x = mon_left + int((roi.x + roi.w / 2) * mon_width)
            click_y = mon_top + int((roi.y + roi.h / 2) * mon_height)

            print(
                f"Clicking {button_name} at global ({click_x}, {click_y}) [Monitor {self.monitor_index} offset: ({mon_left}, {mon_top})]"
            )

            if not self.dry_run:
                pyautogui.click(click_x, click_y)
                time.sleep(0.1)
            else:
                print(f"Dry run: Would click {button_name}")

            return True

        except Exception as e:
            print(f"Error clicking {button_name}: {e}")
            return False

    def navigate_to_red1_base(
        self,
        monitor_index: int,
        base_unit_rois: Dict[str, ROIMeta],
        dry_run: bool = False,
    ) -> bool:
        # Navigate to red1 base by clicking on its ROI area
        try:
            # Find a suitable red1 ROI to click (prefer non-adjustment ROIs)
            red1_roi_names = [
                "R1blight",
                "R1bheavy",
                "R1branged",
                "R1rlight",
                "R1rheavy",
                "R1rranged",
            ]

            for roi_name in red1_roi_names:
                if roi_name in base_unit_rois:
                    roi = base_unit_rois[roi_name]

                    # Get monitor offset position for multi-monitor support
                    import mss

                    with mss.mss() as sct:
                        if monitor_index < 1 or monitor_index >= len(sct.monitors):
                            print(f"Error: Invalid monitor_index {monitor_index}")
                            return False
                        mon = sct.monitors[monitor_index]
                        mon_left = mon["left"]
                        mon_top = mon["top"]
                        mon_width = mon["width"]
                        mon_height = mon["height"]

                    # Convert relative ROI coordinates to absolute screen coordinates
                    # Add monitor offset for multi-monitor setups
                    click_x = mon_left + int((roi.x + roi.w / 2) * mon_width)
                    click_y = mon_top + int((roi.y + roi.h / 2) * mon_height)

                    print(
                        f"Navigating to red1 base by clicking {roi_name} at global ({click_x}, {click_y}) [Monitor {monitor_index} offset: ({mon_left}, {mon_top})]"
                    )

                    if not dry_run:
                        import pyautogui

                        pyautogui.click(click_x, click_y)
                        time.sleep(0.2)  # Wait for navigation to complete
                    else:
                        print("Dry run: Would click on red1 base")

                    return True

            print("Warning: No red1 ROIs found for navigation")
            return False

        except Exception as e:
            print(f"Error navigating to red1 base: {e}")
            return False

    def capture_red2_final_unit_count(
        self, monitor_index: int, red2_final_unit_roi: ROIMeta, dry_run: bool = False
    ) -> Optional[str]:
        # Sample Red2 unit count 5 times over 5 seconds to avoid UI overlays and movement cycles
        if not red2_final_unit_roi:
            print("Error: Red2_FinalUnitCountArea ROI not loaded")
            return None

        print("Capturing Red2 final unit count (5 captures over 5 seconds)...")

        captured_images = []

        # Capture 5 frames at 1-second intervals
        for i in range(5):
            try:
                print(f"  Capture {i+1}/5...")

                # Capture frame
                frame = self.screen_capture.capture_monitor(monitor_index)
                if frame is None:
                    print(f"  Failed to capture frame {i+1}")
                    time.sleep(0.2)
                    continue

                # Crop ROI
                roi_image = ImageUtils.crop_roi(frame, red2_final_unit_roi)

                # Save capture to final_state folder
                self.output_manager.save_capture(
                    roi_image,
                    phase_num="final_state",
                    roi_name=f"Red2_Final_Capture_{i+1}",
                )

                # Store the captured image
                captured_images.append((i + 1, roi_image))

                # Wait 1 second before next capture (except after the last one)
                if i < 4:
                    time.sleep(0.2)

            except Exception as e:
                print(f"  Error capturing frame {i+1}: {e}")
                if i < 4:
                    time.sleep(0.2)

        if not captured_images:
            print("Failed to capture any frames")
            return None

        print(f"Processing OCR on {len(captured_images)} captured images...")

        # Process OCR on all captured images and collect results
        ocr_results = []

        for capture_num, roi_image in captured_images:
            try:
                # Process OCR
                accepted_chars = "0123456789"  # Only numbers expected for unit count
                results = self.ocr_processor.process_multi_engine(
                    roi_image,
                    red2_final_unit_roi,
                    accepted_chars=accepted_chars,
                    early_exit_enabled=True,
                )

                if results:
                    # Get the best result from this capture
                    method_name, _, text, confidence, rule_passed, rule_message = (
                        results[0]
                    )

                    # Only consider valid digit results
                    if text.strip() and text.strip().isdigit():
                        ocr_results.append(
                            (capture_num, text.strip(), confidence, method_name)
                        )
                        print(
                            f"    Capture {capture_num}: '{text}' ({confidence:.1f}%, {method_name})"
                        )
                    else:
                        print(f"    Capture {capture_num}: Invalid text '{text}'")
                else:
                    print(f"    Capture {capture_num}: No OCR results")

            except Exception as e:
                print(f"    Capture {capture_num}: OCR error - {e}")

        if not ocr_results:
            print("No valid OCR results from any capture")
            # Still click reset view button even if capture failed
            self._click_reset_view_button(dry_run)
            return None

        # Find the best result (highest confidence)
        best_result = max(
            ocr_results, key=lambda x: x[2]
        )  # Sort by confidence (index 2)
        capture_num, text, confidence, method_name = best_result

        print(
            f"Best result: Capture {capture_num} - '{text}' ({confidence:.1f}%, {method_name})"
        )

        # Click reset view button to return to normal view
        self._click_reset_view_button(dry_run)

        return text

    def _click_reset_view_button(self, dry_run: bool = False):
        # Helper method to click the reset view button
        print("Clicking reset view button...")
        if self.click_resetview():
            print("Reset view button clicked")
        else:
            print("Warning: Failed to click reset view button")

    def click_downphase(self, times: int = 2) -> bool:
        # Click the down phase button
        if not self.button_rois or "Downphase" not in self.button_rois:
            print("Downphase ROI not loaded")
            return False

        for i in range(times):
            print(f"Clicking downphase button ({i+1}/{times})")
            if not self._click_roi_button(self.button_rois["Downphase"], "Downphase"):
                return False

            if i < times - 1:
                time.sleep(0.2)

        return True

    def click_upphase(self, times: int = 1) -> bool:
        # Click the up phase button
        if not self.button_rois or "Upphase" not in self.button_rois:
            print("Upphase ROI not loaded")
            return False

        for i in range(times):
            print(f"Clicking upphase button ({i+1}/{times})")
            if not self._click_roi_button(self.button_rois["Upphase"], "Upphase"):
                return False

            if i < times - 1:
                time.sleep(0.2)

        return True

    def click_resetview(self) -> bool:
        # Click the reset view button
        if not self.button_rois or "Resetview_button" not in self.button_rois:
            print("Resetview_button ROI not loaded")
            return False

        return self._click_roi_button(self.button_rois["Resetview_button"], "Resetview")

    def init_phase_one(self) -> bool:
        # Initialise game to Phase 1 with Reset View
        print("\n=== Initialising to Phase 1 ===")

        # Click down phase twice to ensure Phase 1, with reset after each
        print("Attempting to navigate to Phase 1...")
        for i in range(2):
            self.click_downphase(times=1)
            time.sleep(0.1)  # Small wait after phase change

            # Reset view after each phase change to guard against camera movement
            print("Resetting view...")
            if not self.click_resetview():
                print("Warning: Could not find reset view button")
            time.sleep(0.1)

        self.current_phase = 1
        print("Successfully initialised to Phase 1")
        return True

    def next_phase(self) -> bool:
        # Advance to the next phase using up button with view reset
        print(f"\n=== Advancing from Phase {self.current_phase} ===")

        # Click up phase
        self.click_upphase()
        time.sleep(0.2)  # Wait for phase transition

        # Reset view after phase change to guard against camera movement
        print("Resetting view...")
        if not self.click_resetview():
            print("Warning: Could not find reset view button")
        time.sleep(0.1)

        self.current_phase += 1
        print(f"Advanced to Phase {self.current_phase}")
        return True

    def clear_cache(self):
        # Clear cached button positions
        self.button_positions.clear()

    def reset(self):
        # Reset controller state
        self.current_phase = 1
        self.clear_cache()
        print("Navigation controller reset")
