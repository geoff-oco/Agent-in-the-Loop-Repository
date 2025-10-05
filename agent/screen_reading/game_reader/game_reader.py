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


class LiveGameReader:  # Main game reader orchestrator

    def __init__(
        self,
        main_roi_path: str = "rois/rois_main/Main_rois.json",
        element_roi_path: str = "rois/rois_main/Element_rois.json",
        monitor_index: int = 3,
        dry_run: bool = False,
        output_dir: str = "output",
    ):
        self.main_roi_path = main_roi_path
        self.element_roi_path = element_roi_path
        self.monitor_index = monitor_index
        self.dry_run = dry_run

        # Core components
        self.ocr_processor = get_ocr_processor()
        self.screen_capture = get_screen_capture()
        self.output_manager = SessionOutputManager(output_dir)
        self.progress_reporter = ProgressReporter()  # Add progress reporter

        # Specialized components
        self.exit_manager = ExitManager()
        self.game_state_manager = GameStateManager(self.screen_capture, self.ocr_processor, monitor_index)
        self.game_ocr_processor = GameOCRProcessor(self.ocr_processor, self.screen_capture, self.output_manager)
        self.navigation_controller = NavigationController(
            self.screen_capture, self.ocr_processor, self.output_manager, dry_run, fast_mode=True
        )

        # Clear any stale progress file at start
        self.progress_reporter.clear()

        # ROI storage
        self.base_unit_rois: Dict[str, ROIMeta] = {}  # Base unit counts
        self.adjustment_rois: Dict[str, ROIMeta] = {}  # Adjustment values
        self.red2_final_unit_roi: Optional[ROIMeta] = None  # Red2 final unit count area

        # Game data
        self.phases: List[PhaseData] = []
        self.initial_ler: Optional[str] = None

    def load_rois(self) -> bool:
        # Load all ROIs from element and main files
        try:
            # Load Phase and LER ROIs from Element file
            if not self.game_state_manager.load_rois(self.element_roi_path):
                print("Failed to load Phase/LER ROIs from Element file")
                return False

            # Load Red2 final unit count ROI from Element file
            element_manager = ROIManager()
            success, message, count = element_manager.load_from_file(self.element_roi_path)
            if success:
                for name, roi in element_manager.rois.items():
                    if name == "Red2_FinalUnitCountArea":
                        self.red2_final_unit_roi = roi
                        print("Found Red2_FinalUnitCountArea ROI in Element ROIs")
                        break

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

    def run(self) -> bool:
        # Main execution flow
        try:
            print("\n" + "=" * 60)
            print("LIVE GAME READER")
            print("=" * 60)

            # Initialise progress reporting
            self.progress_reporter.update("Initialising screen reader...", percentage=5)

            # Start exit monitoring
            self.exit_manager.start_exit_monitoring()
            if hasattr(self.exit_manager, 'exit_thread') and self.exit_manager.exit_thread:
                print("Press 'x' at any time to exit...")
            else:
                print("Use Ctrl+C to exit...")
            print("")

            # Initialise session with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            session_name = f"game_session_{timestamp}"
            self.output_manager.init_session(session_name)

            # Load ROIs
            logging.info("Loading ROI configurations...")
            self.progress_reporter.update("Loading ROI configurations...", percentage=10)
            if not self.load_rois():
                print("Failed to load ROIs")
                logging.error("Failed to load ROI configurations")
                self.progress_reporter.error("Failed to load ROI configurations")
                return False
            logging.info("ROI configurations loaded successfully")
            self.progress_reporter.update("ROI configurations loaded successfully", percentage=15)

            # Step 1: Initial setup
            print("\n=== Initial Setup ===")

            # Reset view at start to ensure consistent camera position
            print("Resetting view to default position...")
            logging.info("Performing initial view reset")
            if not self.navigation_controller.click_resetview():
                print("Warning: Could not find reset view button during initial setup")
                logging.warning("Initial reset view failed - button not found")
            else:
                print("View reset complete")
                logging.info("Initial view reset successful")

            # Read LER
            self.initial_ler = self.game_state_manager.read_ler()
            if not self.initial_ler:
                print("Warning: Could not read LER")
                self.initial_ler = "LER 1.00:1 in favour of Neutral"

            # Read phase header
            phase_header = self.game_state_manager.read_phase_header()
            print(f"Phase header: {phase_header}")

            # Navigate to Phase 1
            self.progress_reporter.update("Navigating to Phase 1...", percentage=20)
            if not self.navigation_controller.init_phase_one():
                print("Failed to initialise to Phase 1")
                if not self.dry_run:
                    self.progress_reporter.error("Failed to initialise to Phase 1")
                    return False

            # Step 2: Process 3 phases
            for phase_num in range(1, 4):
                # Check for exit request
                if self.exit_manager.check_exit_requested():
                    return False

                print(f"\n{'=' * 60}")
                print(f"PHASE {phase_num}")
                print("=" * 60)

                # Update progress for phase
                phase_percentage = 20 + (phase_num * 20)  # 40%, 60%, 80%
                self.progress_reporter.update(f"Processing Phase {phase_num} capture...", phase=phase_num, percentage=phase_percentage)

                # Process OCR for this phase (fresh capture)
                ocr_results = self.game_ocr_processor.process_phase_ocr(
                    phase_num, self.monitor_index, self.base_unit_rois, self.adjustment_rois
                )

                # Calculate before/after states from fresh OCR
                phase_data = self.game_state_manager.calculate_phase_data(phase_num, ocr_results)
                self.phases.append(phase_data)

                # Log phase data
                self._display_phase_summary(phase_data)

                # Advance to next phase (except after phase 3)
                if phase_num < 3:
                    # Check for exit request before advancing
                    if self.exit_manager.check_exit_requested():
                        return False

                    print(f"\nAutomatically advancing to Phase {phase_num + 1}...")
                    advance_percentage = 20 + ((phase_num + 1) * 20) - 5  # Slightly less than next phase start
                    self.progress_reporter.update(f"Advancing to Phase {phase_num + 1}...", phase=phase_num, percentage=advance_percentage)
                    if not self.navigation_controller.next_phase():
                        print(f"Warning: Failed to advance to Phase {phase_num + 1}")

            # Red2 Final Unit Count Capture (after Phase 3)
            print("\n" + "=" * 60)
            print("RED2 FINAL UNIT COUNT CAPTURE")
            print("=" * 60)
            self.progress_reporter.update("Capturing final unit counts...", phase=3, percentage=85)

            red2_final_count = None
            if self.red2_final_unit_roi:
                # Navigate to red1 base first
                if self.navigation_controller.navigate_to_red1_base(
                    self.monitor_index, self.base_unit_rois, self.dry_run
                ):
                    # Wait a moment for navigation to complete
                    time.sleep(0.5)

                    # Capture the dynamic Red2 final unit count
                    red2_final_count = self.navigation_controller.capture_red2_final_unit_count(
                        self.monitor_index, self.red2_final_unit_roi, self.dry_run
                    )

                    if red2_final_count:
                        print(f"Successfully captured Red2 final unit count: {red2_final_count}")
                    else:
                        print("Failed to capture Red2 final unit count")
                else:
                    print("Failed to navigate to red1 base for Red2 capture")
            else:
                print("Red2_FinalUnitCountArea ROI not available - skipping capture")

            # Step 3: Generate output
            print("\n=== Generating Output ===")
            self.progress_reporter.update("Generating game state data...", percentage=90)

            # Build output JSON (red2_final_count used for calculations but not exported)
            output_data = {
                "meta": {
                    "ler": self.game_state_manager.calculate_ler(self.initial_ler),
                },
                "phases": [phase.to_dict() for phase in self.phases],
                "final_state": {
                    name: units.to_dict()
                    for name, units in self.game_state_manager.get_final_state(self.phases, red2_final_count).items()
                },
            }

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
                "avg_phase_duration": round(stats["duration_seconds"] / len(self.phases), 2) if self.phases else 0,
                "total_ocr_operations": stats["total_base_rois"] * len(self.phases)
                + stats["total_adjustment_rois"] * len(self.phases),
                "captures_per_phase": round(stats["captures_saved"] / len(self.phases), 1) if self.phases else 0,
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
        for base_name in sorted(base_names):
            if base_name in phase_data.after:
                units = phase_data.after[base_name]
                print(
                    f"    {base_name} Blue: L={units.blue.L}, H={units.blue.H}, R={units.blue.R} | Red: L={units.red.L}, H={units.red.H}, R={units.red.R}"
                )
            else:
                print(f"    {base_name} Blue: L=0, H=0, R=0 | Red: L=0, H=0, R=0")