# Game navigation and automation controller
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import pyautogui

from core.models import ROIMeta
from imaging.utils import ImageUtils


class NavigationController:  # Handles game navigation and special capture sequences

    def __init__(self, screen_capture, ocr_processor, output_manager, dry_run: bool = False):
        self.screen_capture = screen_capture
        self.ocr_processor = ocr_processor
        self.output_manager = output_manager
        self.dry_run = dry_run

        # Navigation state
        self.current_phase: int = 1

        # Template-based button clicking setup
        self.template_dir = Path("rois/template_images")
        self.button_positions: Dict[str, Tuple[int, int]] = {}

        # Configure PyAutoGUI
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

        # Load button templates
        self.templates = {
            "upphase": self.template_dir / "Upphase_button.png",
            "downphase": self.template_dir / "Downphase_button.png",
            "resetview": self.template_dir / "Resetview_button.png",
        }

    def navigate_to_red1_base(
        self, monitor_index: int, base_unit_rois: Dict[str, ROIMeta], dry_run: bool = False
    ) -> bool:
        # Navigate to red1 base by clicking on its ROI area
        try:
            # Find a suitable red1 ROI to click (prefer non-adjustment ROIs)
            red1_roi_names = ["R1blight", "R1bheavy", "R1branged", "R1rlight", "R1rheavy", "R1rranged"]

            for roi_name in red1_roi_names:
                if roi_name in base_unit_rois:
                    roi = base_unit_rois[roi_name]

                    # Calculate click position (center of ROI)
                    # Convert relative coordinates to absolute screen coordinates
                    frame = self.screen_capture.capture_monitor(monitor_index)
                    if frame is None:
                        print("Failed to capture screen for navigation")
                        return False

                    screen_width, screen_height = frame.size
                    click_x = int((roi.x + roi.w / 2) * screen_width)
                    click_y = int((roi.y + roi.h / 2) * screen_height)

                    print(f"Navigating to red1 base by clicking {roi_name} at ({click_x}, {click_y})")

                    if not dry_run:
                        import pyautogui

                        pyautogui.click(click_x, click_y)
                        time.sleep(1.0)  # Wait for navigation to complete
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
                    time.sleep(1.0)
                    continue

                # Crop ROI
                roi_image = ImageUtils.crop_roi(frame, red2_final_unit_roi)

                # Save debug image for this capture
                self.output_manager.save_capture(roi_image, phase_num=99, roi_name=f"Red2_Final_Capture_{i+1}")

                # Store the captured image
                captured_images.append((i + 1, roi_image))

                # Wait 1 second before next capture (except after the last one)
                if i < 4:
                    time.sleep(1.0)

            except Exception as e:
                print(f"  Error capturing frame {i+1}: {e}")
                if i < 4:
                    time.sleep(1.0)

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
                    roi_image, red2_final_unit_roi, accepted_chars=accepted_chars, early_exit_enabled=True
                )

                if results:
                    # Get the best result from this capture
                    method_name, _, text, confidence, rule_passed, rule_message = results[0]

                    # Only consider valid digit results
                    if text.strip() and text.strip().isdigit():
                        ocr_results.append((capture_num, text.strip(), confidence, method_name))
                        print(f"    Capture {capture_num}: '{text}' ({confidence:.1f}%, {method_name})")
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
        best_result = max(ocr_results, key=lambda x: x[2])  # Sort by confidence (index 2)
        capture_num, text, confidence, method_name = best_result

        print(f"Best result: Capture {capture_num} - '{text}' ({confidence:.1f}%, {method_name})")

        # Click reset view button to return to normal view
        self._click_reset_view_button(dry_run)

        return text

    def _click_reset_view_button(self, dry_run: bool = False):
        # Helper method to click the reset view button
        print("Clicking reset view button...")
        reset_position = self.find_button("resetview", confidence=0.8, cache=False)
        if reset_position:
            if not dry_run:
                pyautogui.click(reset_position)
                time.sleep(0.5)  # Brief pause after click
                print("Reset view button clicked")
            else:
                print("Dry run: Would click reset view button")
        else:
            print("Warning: Reset view button not found")

    def find_button(
        self, button_name: str, confidence: float = 0.8, cache: bool = True
    ) -> Optional[Tuple[int, int]]:
        # Find button on screen using template matching
        # Check cache first
        if cache and button_name in self.button_positions:
            return self.button_positions[button_name]

        if button_name not in self.templates:
            return None

        template_path = self.templates[button_name]
        if not template_path.exists():
            return None

        try:
            print(f"Searching for {button_name} button...")

            # Try to locate button on screen
            location = pyautogui.locateCenterOnScreen(str(template_path), confidence=confidence, grayscale=False)

            if location:
                position = (location.x, location.y)
                print(f"Found {button_name} button at {position}")

                # Cache the position
                if cache:
                    self.button_positions[button_name] = position

                return position
            else:
                # Don't print error for first attempts, just return None
                if confidence > 0.6:
                    return self.find_button(button_name, confidence - 0.1, cache)

                # Only print if we've tried all confidence levels
                print(f"Could not find {button_name} button on screen")
                return None

        except Exception as e:
            # Only print real exceptions, not "button not found"
            if "could not be found" not in str(e).lower():
                print(f"Error finding button {button_name}: {e}")
            return None

    def click_downphase(self, times: int = 2) -> bool:
        # Click the down phase button
        for i in range(times):
            position = self.find_button("downphase", cache=False)  # Always find fresh

            if not position:
                print("Downphase button not found - likely already at Phase 1")
                return True  # Not a failure, we're already where we want to be

            x, y = position
            if self.dry_run:
                print(f"DRY RUN: Would click downphase at ({x}, {y}) ({i+1}/{times})")
            else:
                print(f"Clicking downphase button ({i+1}/{times})")
                pyautogui.moveTo(x, y, duration=0.3)
                time.sleep(0.1)
                pyautogui.click()

            if i < times - 1:
                time.sleep(0.8)

        return True

    def click_upphase(self, times: int = 1) -> bool:
        # Click the up phase button
        for i in range(times):
            position = self.find_button("upphase", cache=False)  # Always find fresh

            if not position:
                print("Upphase button not found - likely already at Phase 3")
                return True  # Not a failure, we're at the max phase

            x, y = position
            if self.dry_run:
                print(f"DRY RUN: Would click upphase at ({x}, {y}) ({i+1}/{times})")
            else:
                print(f"Clicking upphase button ({i+1}/{times})")
                pyautogui.moveTo(x, y, duration=0.3)
                time.sleep(0.1)
                pyautogui.click()

            if i < times - 1:
                time.sleep(0.8)

        return True

    def click_resetview(self) -> bool:
        # Click the reset view button
        position = self.find_button("resetview", cache=False)

        if not position:
            print("Reset view button not found")
            return False

        x, y = position
        if self.dry_run:
            print(f"DRY RUN: Would click resetview at ({x}, {y})")
        else:
            print("Clicking reset view button")
            pyautogui.moveTo(x, y, duration=0.3)
            time.sleep(0.1)
            pyautogui.click()

        return True

    def init_phase_one(self) -> bool:
        # Initialise game to Phase 1 with Reset View
        print("\n=== Initialising to Phase 1 ===")

        # Click down phase twice to ensure Phase 1, with reset after each
        print("Attempting to navigate to Phase 1...")
        for i in range(2):
            self.click_downphase(times=1)
            time.sleep(0.5)  # Small wait after phase change

            # Reset view after each phase change to guard against camera movement
            print("Resetting view...")
            if not self.click_resetview():
                print("Warning: Could not find reset view button")
            time.sleep(0.5)

        self.current_phase = 1
        print("Successfully initialised to Phase 1")
        return True

    def next_phase(self) -> bool:
        # Advance to the next phase using up button with view reset
        print(f"\n=== Advancing from Phase {self.current_phase} ===")

        # Click up phase
        self.click_upphase()
        time.sleep(1.0)  # Wait for phase transition

        # Reset view after phase change to guard against camera movement
        print("Resetting view...")
        if not self.click_resetview():
            print("Warning: Could not find reset view button")
        time.sleep(0.5)

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