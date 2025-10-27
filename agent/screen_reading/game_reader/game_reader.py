#!/usr/bin/env python3
# Live game reader with modular architecture

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from core.models import ROIMeta
from core.roi_manager import ROIManager
from imaging.capture import get_screen_capture
from ocr.processor import get_ocr_processor

from .exit_manager import ExitManager
from .game_state_manager import GameStateManager
from .models import PhaseData
from .navigation_controller import NavigationController
from .ocr_processor import GameOCRProcessor
from .progress_reporter import ProgressReporter
from .session_output_manager import SessionOutputManager
from .stats_reporter import StatsReporter


class LiveGameReader:  # Main game reader orchestrator

    def __init__(
        self,
        main_roi_path: str = "rois/rois_main/Main_rois_custom.json",
        element_roi_path: str = "rois/rois_main/Element_rois_custom.json",
        monitor_index: int = None,  # None = auto-detect RTSViewer monitor
        dry_run: bool = False,
        output_dir: str = "output",
    ):
        self.main_roi_path_template = main_roi_path  # Template path for fallback
        self.element_roi_path_template = element_roi_path  # Template path for fallback
        self.main_roi_path = main_roi_path  # Will be updated with resolution-specific path
        self.element_roi_path = element_roi_path  # Will be updated with resolution-specific path
        self.monitor_index = monitor_index  # Will be auto-detected if None
        self.dry_run = dry_run

        # Core components
        self.ocr_processor = get_ocr_processor()
        self.screen_capture = get_screen_capture()
        self.output_manager = SessionOutputManager(output_dir)
        self.progress_reporter = ProgressReporter()
        self.stats_reporter = None  # Initialised after session creation

        # Specialized components
        self.exit_manager = ExitManager()
        self.game_state_manager = GameStateManager(
            self.screen_capture, self.ocr_processor, monitor_index, self.output_manager
        )
        self.game_ocr_processor = GameOCRProcessor(self.ocr_processor, self.screen_capture, self.output_manager)
        self.navigation_controller = NavigationController(
            self.screen_capture,
            self.ocr_processor,
            self.output_manager,
            dry_run,
            fast_mode=True,
        )

        # Clear any stale progress file at start
        self.progress_reporter.clear()

        # ROI storage
        self.base_unit_rois: Dict[str, ROIMeta] = {}  # Base unit counts
        self.adjustment_rois: Dict[str, ROIMeta] = {}  # Adjustment values
        self.red2_final_unit_roi: Optional[ROIMeta] = None  # Red2 final unit count area
        self.button_rois: Dict[str, ROIMeta] = {}  # Navigation button ROIs

        # Game data
        self.phases: List[PhaseData] = []
        self.initial_ler: Optional[str] = None
        self.actions_by_phase: Optional[Dict[int, List]] = None  # Actions from save_state.json

    def get_monitor_resolution(self, monitor_index: int) -> tuple[int, int]:
        try:
            import mss

            with mss.mss() as sct:
                if monitor_index < 1 or monitor_index >= len(sct.monitors):
                    monitor_index = 1
                mon = sct.monitors[monitor_index]
                return mon["width"], mon["height"]
        except Exception as e:
            logging.error(f"Failed to get monitor resolution: {e}")
            return 1920, 1080

    def build_resolution_specific_roi_path(self, base_path: str, width: int, height: int) -> str:
        # Extract directory and filename components
        dir_name = os.path.dirname(base_path)
        file_name = os.path.basename(base_path)
        name_without_ext = os.path.splitext(file_name)[0]
        ext = os.path.splitext(file_name)[1]

        # Remove _custom suffix if present for building resolution-specific name
        base_name = name_without_ext.replace("_custom", "")

        # Build resolution-specific path: Main_rois_2560x1440.json
        resolution_specific_path = os.path.join(dir_name, f"{base_name}_{width}x{height}{ext}")

        # Check if resolution-specific file exists
        if os.path.exists(resolution_specific_path):
            logging.info(f"Using resolution-specific ROI file: {resolution_specific_path}")
            print(f"Using resolution-specific ROI file: {os.path.basename(resolution_specific_path)}")
            return resolution_specific_path
        else:
            logging.info(
                f"Resolution-specific ROI file not found: {resolution_specific_path}, using custom fallback: {base_path}"
            )
            print(
                f"Resolution-specific ROI file not found ({width}x{height}), using custom fallback: {os.path.basename(base_path)}"
            )
            return base_path

    def detect_rtsviewer_monitor(self) -> Optional[int]:
        # Auto-detect which monitor contains RTSViewer window
        try:
            import win32gui
            import mss

            # Find RTSViewer window
            hwnd = win32gui.FindWindow(None, "RTSViewer")
            if not hwnd:
                print("WARNING: RTSViewer window not found - using monitor 1 as fallback")
                logging.warning("RTSViewer window not found for monitor detection")
                return 1

            # Get window position
            rect = win32gui.GetWindowRect(hwnd)
            window_left, window_top, window_right, window_bottom = rect
            window_center_x = (window_left + window_right) // 2
            window_center_y = (window_top + window_bottom) // 2

            print(f"RTSViewer window found at: ({window_left}, {window_top}) to ({window_right}, {window_bottom})")
            print(f"Window center: ({window_center_x}, {window_center_y})")

            # Get all monitors with position data from MSS
            with mss.mss() as sct:
                for i in range(1, len(sct.monitors)):  # Skip index 0 (all monitors combined)
                    mon = sct.monitors[i]
                    mon_left = mon["left"]
                    mon_top = mon["top"]
                    mon_right = mon_left + mon["width"]
                    mon_bottom = mon_top + mon["height"]

                    print(
                        f"Monitor {i}: ({mon_left}, {mon_top}) to ({mon_right}, {mon_bottom}) - {mon['width']}x{mon['height']}"
                    )

                    # Check if window center is within this monitor's bounds
                    if mon_left <= window_center_x < mon_right and mon_top <= window_center_y < mon_bottom:
                        print(f"RTSViewer detected on Monitor {i}: {mon['width']}x{mon['height']}")
                        logging.info(f"Auto-detected RTSViewer on monitor {i} ({mon['width']}x{mon['height']})")
                        return i

            # Fallback if window not found in any monitor bounds
            print(f"WARNING: RTSViewer window not within any monitor bounds - using monitor 1 as fallback")
            logging.warning("RTSViewer window position outside all monitor bounds")
            return 1

        except Exception as e:
            print(f"ERROR detecting RTSViewer monitor: {e}")
            logging.error(f"Monitor detection failed: {e}")
            return 1

    def load_rois(self) -> bool:
        # Load all ROIs from element and main files
        try:
            # Load Phase and LER ROIs from Element file
            if not self.game_state_manager.load_rois(self.element_roi_path):
                print("Failed to load Phase/LER ROIs from Element file")
                return False

            # Load Red2 final unit count ROI and navigation button ROIs from Element file
            element_manager = ROIManager()
            success, message, count = element_manager.load_from_file(self.element_roi_path)
            if success:
                for name, roi in element_manager.rois.items():
                    if name == "Red2_FinalUnitCountArea":
                        self.red2_final_unit_roi = roi
                        print("Found Red2_FinalUnitCountArea ROI in Element ROIs")
                    elif name in ["Upphase", "Downphase", "Resetview_button"]:
                        self.button_rois[name] = roi
                        print(f"Found {name} button ROI in Element ROIs")

            # Load unit count ROIs from Main file
            manager = ROIManager()
            success, message, count = manager.load_from_file(self.main_roi_path)
            if not success:
                print(f"Failed to load main ROIs: {message}")
                return False

            # Categorise unit ROIs into base counts and adjustments
            for name, roi in manager.rois.items():
                if "_adj" in name.lower():
                    # This is an adjustment ROI
                    self.adjustment_rois[name] = roi
                else:
                    # This is a base unit count ROI
                    self.base_unit_rois[name] = roi

            print(f"Loaded {len(self.base_unit_rois)} base unit ROIs")
            print(f"Loaded {len(self.adjustment_rois)} adjustment ROIs")
            if self.red2_final_unit_roi:
                print("Loaded Red2_FinalUnitCountArea ROI")

            return True

        except Exception as e:
            print(f"Error loading ROIs: {e}")
            return False

    def run(self, skip_save_check: bool = False, phase_selection: Optional[int] = None) -> bool:
        # Main execution flow with smart capture planning
        try:
            print("\n" + "=" * 60)
            print("LIVE GAME READER")
            print("=" * 60)

            # Initialise progress reporting
            self.progress_reporter.update("Initialising screen reader...", percentage=5)

            # Start exit monitoring
            self.exit_manager.start_exit_monitoring()
            if hasattr(self.exit_manager, "exit_thread") and self.exit_manager.exit_thread:
                print("Press 'x' at any time to exit...")
            else:
                print("Use Ctrl+C to exit...")
            print("")

            # Initialise session with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            session_name = f"game_session_{timestamp}"
            self.output_manager.init_session(session_name)

            # Initialise stats reporter with session-specific path
            self.stats_reporter = StatsReporter(self.output_manager.get_stats_file_path())
            self.stats_reporter.clear()

            # Auto-detect monitor if not specified (BEFORE loading ROIs)
            if self.monitor_index is None:
                print("\n=== Monitor Detection ===")
                self.monitor_index = self.detect_rtsviewer_monitor()
                print(f"Using Monitor {self.monitor_index}")
                # Update game_state_manager with detected monitor
                self.game_state_manager.monitor_index = self.monitor_index

            # Detect monitor resolution and update ROI paths (BEFORE loading ROIs)
            width, height = self.get_monitor_resolution(self.monitor_index)
            print(f"Monitor resolution detected: {width}x{height}")
            logging.info(f"Monitor {self.monitor_index} resolution: {width}x{height}")

            # Build resolution-specific ROI paths
            self.main_roi_path = self.build_resolution_specific_roi_path(self.main_roi_path_template, width, height)
            self.element_roi_path = self.build_resolution_specific_roi_path(
                self.element_roi_path_template, width, height
            )

            # Load ROIs (now with resolution-specific paths)
            logging.info("Loading ROI configurations...")
            self.progress_reporter.update("Loading ROI configurations...", percentage=10)
            if not self.load_rois():
                print("Failed to load ROIs")
                logging.error("Failed to load ROI configurations")
                self.progress_reporter.error("Failed to load ROI configurations")
                return False
            logging.info("ROI configurations loaded successfully")
            self.progress_reporter.update("ROI configurations loaded successfully", percentage=15)

            # Set button ROIs and monitor index on NavigationController
            self.navigation_controller.button_rois = self.button_rois
            self.navigation_controller.monitor_index = self.monitor_index
            print(f"NavigationController configured with {len(self.button_rois)} button ROIs")

            # SMART CAPTURE PLANNING - Check for save_state.json before any navigation
            print("\n=== Smart Capture Planning ===")
            from .smart_capture_planner import SmartCapturePlanner

            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            capture_plan = None

            # Step 1: Check for save_state.json
            save_state_exists, save_state_data = SmartCapturePlanner.check_save_state(project_root)

            if save_state_exists:
                # Parse actions and generate capture plan from save_state
                self.actions_by_phase = SmartCapturePlanner.parse_actions_from_save_state(save_state_data)
                capture_plan = SmartCapturePlanner.calculate_capture_plan_from_save_state(self.actions_by_phase)
                logging.info("Save state detected - using enriched capture plan")
                print(f"Save state detected - Capture plan generated from save_state.json")
                print(f"  Phases to capture: {capture_plan['phases_to_capture']}")
                print(f"  Phase modes: {capture_plan['phase_modes']}")
                print(f"  Red2 final needed: {capture_plan['needs_red2_final']}")

            elif phase_selection is not None:
                # User provided phase selection via UI popup
                logging.info(f"Using user phase selection: phase {phase_selection} has no actions")
                print(f"Using user-provided phase selection: phase {phase_selection} has no actions")
                capture_plan = SmartCapturePlanner.calculate_capture_plan_from_user_selection(phase_selection)
                print(f"  Phases to capture: {capture_plan['phases_to_capture']}")
                print(f"  Phase modes: {capture_plan['phase_modes']}")
                print(f"  Red2 final needed: {capture_plan['needs_red2_final']}")

            else:
                # No save_state and no user selection - default to full 3-phase capture
                logging.info("No save_state - defaulting to simple 3-phase capture")
                print("No save_state.json found and no user selection - defaulting to full 3-phase capture")
                capture_plan = {
                    "phases_to_capture": [1, 2, 3],
                    "phase_modes": {1: "full", 2: "full", 3: "full"},
                    "needs_red2_final": True,
                    "export_mode": "simple",
                }

            print(f"\nCapture plan finalised:")
            print(f"  Phases: {capture_plan['phases_to_capture']}")
            print(f"  Modes: {capture_plan['phase_modes']}")
            print(f"  Red2 final: {capture_plan['needs_red2_final']}")
            print(f"  Export mode: {capture_plan['export_mode']}")
            self.progress_reporter.update("Capture plan ready", percentage=18)

            # Initial LER reading (before navigation) - uses standalone processing
            print("\n=== Initial Setup ===")
            self.initial_ler = self.game_state_manager.read_ler()
            if not self.initial_ler:
                print("Warning: Could not read LER")
                self.initial_ler = "LER 1.00:1 in favour of Neutral"
            print(f"LER: {self.initial_ler}")

            # Calculate total OCR tasks for progress tracking
            total_ocr_tasks = 1  # LER task (already completed)

            # Count phase tasks
            for phase_num in capture_plan["phases_to_capture"]:
                mode = capture_plan["phase_modes"][phase_num]
                total_ocr_tasks += len(self.base_unit_rois)  # Base unit ROIs
                if mode == "full":
                    total_ocr_tasks += len(self.adjustment_rois)  # Adjustment ROIs

            # Count Red2 final tasks
            if capture_plan["needs_red2_final"]:
                total_ocr_tasks += 5  # 5 Red2 final captures

            print(f"\nTotal OCR tasks: {total_ocr_tasks}")
            print(f"  LER: 1 task (complete)")
            print(f"  Phase ROIs: {total_ocr_tasks - 1 - (5 if capture_plan['needs_red2_final'] else 0)} tasks")
            if capture_plan["needs_red2_final"]:
                print(f"  Red2 final: 5 tasks")

            # BULK CAPTURE - Execute capture plan
            print("\n=== Bulk Screenshot Capture ===")
            from .bulk_capture_manager import BulkCaptureManager
            from .bulk_ocr_processor import BulkOCRProcessor

            # Initialise bulk capture manager
            capture_manager = BulkCaptureManager(
                self.screen_capture, self.navigation_controller, self.progress_reporter
            )

            # Execute captures based on plan
            self.progress_reporter.update("Executing bulk screenshot capture...", percentage=20)
            capture_results = capture_manager.execute_capture_plan(
                capture_plan, self.monitor_index, self.base_unit_rois
            )

            # Extract captured data
            phase_screenshots = capture_results["phase_screenshots"]
            red2_final_screenshots = capture_results["red2_final_screenshots"]

            print(f"Bulk capture complete: {len(phase_screenshots)} phases captured")
            if red2_final_screenshots:
                print(f"Red2 final: {len(red2_final_screenshots)} frames captured for averaging")

            # BULK OCR PROCESSING - Process all screenshots
            print("\n=== Bulk OCR Processing ===")
            ocr_processor = BulkOCRProcessor(
                self.game_ocr_processor,  # Pass GameOCRProcessor for full OCR logic
                self.progress_reporter,
                # max_workers auto-configured in BulkOCRProcessor (default: 4, min: 2)
            )

            # Process phase screenshots with total task count for accurate progress
            phase_ocr_results = ocr_processor.process_bulk_captures(
                phase_screenshots,
                capture_plan["phase_modes"],
                self.base_unit_rois,
                self.adjustment_rois,
                total_ocr_tasks,
            )

            logging.debug(f"OCR results returned for phases: {list(phase_ocr_results.keys())}")
            logging.debug(f"Capture plan expected phases: {capture_plan['phases_to_capture']}")

            # Process red2 final screenshots if captured
            red2_final_count = None
            if red2_final_screenshots and len(red2_final_screenshots) > 0:
                # Pass single ROI, not dict (red2 is single number, not L/H/R breakdown)
                red2_final_count = ocr_processor.process_red2_final_screenshots(
                    red2_final_screenshots, self.red2_final_unit_roi
                )

            # GAME STATE CONSTRUCTION - Build phase data from OCR results
            print("\n=== Constructing Game State ===")
            for phase_num in capture_plan["phases_to_capture"]:
                if phase_num not in phase_ocr_results:
                    logging.warning(f"Phase {phase_num} missing from OCR results")
                    continue

                ocr_data = phase_ocr_results[phase_num]
                phase_mode = capture_plan["phase_modes"][phase_num]

                # Calculate phase data (handles "full" vs "before_only" modes)
                phase_data = self.game_state_manager.calculate_phase_data(phase_num, ocr_data, mode=phase_mode)
                self.phases.append(phase_data)

                # Display summary
                print(f"\nPhase {phase_num} ({phase_mode} mode):")
                self._display_phase_summary(phase_data)

            # Step 3: Generate output
            print("\n=== Generating Output ===")
            self.progress_reporter.update("Generating game state data...", percentage=90)

            # Ensure all 3 phases are present in output (fill missing with empty placeholders)
            phases_dict = {phase.phase_number: phase for phase in self.phases}
            all_phases = []
            for phase_num in [1, 2, 3]:
                if phase_num in phases_dict:
                    all_phases.append(phases_dict[phase_num].to_dict())
                else:
                    # Create empty placeholder for missing phase
                    all_phases.append(self._create_empty_phase(phase_num))

            # Strip actions field for simple mode (no save_state)
            export_mode = capture_plan.get("export_mode", "simple")
            if export_mode == "simple":
                for phase_dict in all_phases:
                    if "actions" in phase_dict:
                        del phase_dict["actions"]

            # Calculate final state for stats reporting
            final_state = self.game_state_manager.get_final_state(self.phases, red2_final_count)

            # Build output JSON (red2_final_count used for calculations but not exported)
            output_data = {
                "meta": {
                    "ler": self.game_state_manager.calculate_ler(self.initial_ler),
                },
                "phases": all_phases,
                "final_state": {name: units.to_dict() for name, units in final_state.items()},
            }

            # Update stats file with final state (for units remaining/lost calculations)
            self.stats_reporter.update(self.phases, self.actions_by_phase, final_state)

            # Save JSON
            output_file = self.output_manager.export_state(output_data)
            print(f"Saved game state to: {output_file}")
            self.progress_reporter.update("Saving game state to file...", percentage=95)

            # Check for save state file and merge if present
            print("\n=== Checking for Save State File ===")
            # Look for save_state.json in project root (3 levels up: game_reader -> screen_reading -> agent -> root)
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            save_state_path = os.path.join(project_root, "save_state.json")
            print(f"Looking for save state at: {save_state_path}")

            if os.path.exists(save_state_path):
                print("Save state detected! Merging with OCR data...")
                self.progress_reporter.update("Merging save state with OCR data...", percentage=96)

                try:
                    # Import merger
                    from parsers.game_state_merger import GameStateMerger

                    merger = GameStateMerger()

                    # Get output directory (where game_state.json is saved)
                    output_dir = os.path.dirname(output_file)

                    # Merge and export
                    success, final_filename = merger.merge(output_file, save_state_path, output_dir)

                    if success:
                        print(f"SUCCESS: Enriched game state created: {os.path.basename(final_filename)}")
                        print("SUCCESS: Save state file cleaned up")
                    else:
                        print(f"WARNING: Merge failed, using simple export: {os.path.basename(final_filename)}")

                except Exception as e:
                    print(f"ERROR: Error during merge: {e}")
                    print("Continuing with OCR-only export...")
                    logging.error(f"Save state merge failed: {e}", exc_info=True)
            else:
                print("No save state detected - using simple export")
                self.progress_reporter.update("Finalising game state export...", percentage=96)

                # Rename to simple_game_state.json to indicate OCR-only mode
                try:
                    output_dir = os.path.dirname(output_file)
                    simple_output_file = os.path.join(output_dir, "simple_game_state.json")

                    # Rename the file
                    os.rename(output_file, simple_output_file)
                    print(f"SUCCESS: Renamed to simple_game_state.json (OCR-only mode)")

                except Exception as e:
                    print(f"Warning: Could not rename to simple_game_state.json: {e}")
                    logging.warning(f"Failed to rename to simple export: {e}")

            # Enhanced session performance logging
            stats = self.output_manager.get_stats()
            stats["phases_processed"] = len(self.phases)
            stats["total_base_rois"] = len(self.base_unit_rois)
            stats["total_adjustment_rois"] = len(self.adjustment_rois)
            stats["session_performance"] = {
                "avg_phase_duration": (round(stats["duration_seconds"] / len(self.phases), 2) if self.phases else 0),
                "total_ocr_operations": stats["total_base_rois"] * len(self.phases)
                + stats["total_adjustment_rois"] * len(self.phases),
                "captures_per_phase": (round(stats["captures_saved"] / len(self.phases), 1) if self.phases else 0),
            }

            logging.info(f"Session performance summary:")
            logging.info(f"  Total duration: {stats['duration_seconds']:.2f}s")
            logging.info(f"  Phases processed: {stats['phases_processed']}")
            logging.info(f"  Average phase duration: {stats['session_performance']['avg_phase_duration']:.2f}s")
            logging.info(f"  Total OCR operations: {stats['session_performance']['total_ocr_operations']}")
            logging.info(f"  Images captured: {stats['captures_saved']}")
            logging.info(f"Session complete: {json.dumps(stats, indent=2)}")

            # Clean up session
            self.output_manager.cleanup()

            print("\n" + "=" * 60)
            print("GAME READING COMPLETE")
            print("=" * 60)

            # Mark progress as complete
            self.progress_reporter.complete("Screen reading complete! Game state generated.")

            return True

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            self.progress_reporter.error("Process interrupted by user")
            return False

        except Exception as e:
            print(f"\nError: {e}")
            logging.error(f"Game reading error: {e}", exc_info=True)
            self.progress_reporter.error(str(e))
            return False

    def _display_phase_summary(self, phase_data: PhaseData):
        # Display phase before/after summary
        base_names = self.game_state_manager.base_names

        print(f"\n  Before state (with zeroing applied):")
        for base_name in sorted(base_names):
            if base_name in phase_data.before:
                units = phase_data.before[base_name]
                print(
                    f"    {base_name} Blue: L={units.blue.L}, H={units.blue.H}, R={units.blue.R} | Red: L={units.red.L}, H={units.red.H}, R={units.red.R}"
                )
            else:
                print(f"    {base_name} Blue: L=0, H=0, R=0 | Red: L=0, H=0, R=0")

        print(f"\n  After state (with adjustments applied):")
        if phase_data.after is not None:
            for base_name in sorted(base_names):
                if base_name in phase_data.after:
                    units = phase_data.after[base_name]
                    print(
                        f"    {base_name} Blue: L={units.blue.L}, H={units.blue.H}, R={units.blue.R} | Red: L={units.red.L}, H={units.red.H}, R={units.red.R}"
                    )
                else:
                    print(f"    {base_name} Blue: L=0, H=0, R=0 | Red: L=0, H=0, R=0")
        else:
            print(f"    (No actions in this phase - before_only mode)")

    def _create_empty_phase(self, phase_num: int) -> dict:
        # Create empty placeholder phase for consistent 3-phase structure
        # Matches the same structure as a "before_only" phase with no data
        return {"phase": phase_num, "start": {}, "actions": [], "after": {}}
