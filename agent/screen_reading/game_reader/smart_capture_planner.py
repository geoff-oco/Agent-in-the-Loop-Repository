# Smart capture planning based on save_state.json presence and action card analysis
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class SmartCapturePlanner:
    @staticmethod
    def check_save_state(project_root: str) -> Tuple[bool, Optional[Dict]]:
        # Check for save_state.json in project root, return (exists, parsed_data)
        save_state_path = Path(project_root) / "save_state.json"

        if not save_state_path.exists():
            logging.info(f"save_state.json not found at: {save_state_path}")
            return False, None

        try:
            with open(save_state_path, "r", encoding="utf-8") as f:
                save_state_data = json.load(f)
            logging.info(f"save_state.json loaded successfully from: {save_state_path}")
            return True, save_state_data
        except json.JSONDecodeError as e:
            logging.error(f"Malformed save_state.json: {e}")
            return False, None
        except Exception as e:
            logging.error(f"Error reading save_state.json: {e}", exc_info=True)
            return False, None

    @staticmethod
    def parse_actions_from_save_state(save_state_data: Dict) -> Dict[int, List]:
        # Extract which phases have actions: {1: [...actions...], 2: [], 3: [...]}
        allocations = save_state_data.get("Allocations", [])

        # Group allocations by phase
        actions_by_phase = {1: [], 2: [], 3: []}

        for allocation in allocations:
            phase = allocation.get("Phase", 0)
            if 1 <= phase <= 3:
                actions_by_phase[phase].append(allocation)

        logging.info(
            f"Actions by phase: P1={len(actions_by_phase[1])}, "
            f"P2={len(actions_by_phase[2])}, P3={len(actions_by_phase[3])}"
        )

        return actions_by_phase

    @staticmethod
    def calculate_capture_plan_from_save_state(actions_by_phase: Dict[int, List]) -> Dict:
        # Determine capture plan based on which phases have actions
        # Returns: {
        #   "phases_to_capture": [1, 2, 3],
        #   "phase_modes": {1: "full", 2: "before_only", 3: "full"},
        #   "needs_red2_final": bool,
        #   "export_mode": "enriched"
        # }

        phases_to_capture = []
        phase_modes = {}
        needs_red2_final = False

        # Phase 1
        if len(actions_by_phase[1]) > 0:
            phases_to_capture.append(1)
            phase_modes[1] = "full"  # Has actions, need before + after
        else:
            phases_to_capture.append(1)
            phase_modes[1] = "before_only"  # No actions, just before state

        # Phase 2
        if len(actions_by_phase[2]) > 0:
            phases_to_capture.append(2)
            phase_modes[2] = "full"  # Has actions, need before + after
        elif len(actions_by_phase[1]) > 0:
            # Phase 1 had actions, so we need Phase 2's before (battle results)
            phases_to_capture.append(2)
            phase_modes[2] = "before_only"
        # If Phase 1 also had no actions, we don't need Phase 2 at all

        # Phase 3
        if len(actions_by_phase[3]) > 0:
            phases_to_capture.append(3)
            phase_modes[3] = "full"  # Has actions, need before + after
            needs_red2_final = True  # Only need red2 final if Phase 3 has actions
        elif len(actions_by_phase[2]) > 0:
            # Phase 2 had actions, so we need Phase 3's before (battle results)
            phases_to_capture.append(3)
            phase_modes[3] = "before_only"
        # If Phase 2 also had no actions, we don't need Phase 3 at all

        plan = {
            "phases_to_capture": phases_to_capture,
            "phase_modes": phase_modes,
            "needs_red2_final": needs_red2_final,
            "export_mode": "enriched",  # save_state present means enriched export
        }

        logging.info(f"Capture plan from save_state: {plan}")
        return plan

    @staticmethod
    def calculate_capture_plan_from_user_selection(phase_with_no_actions: int) -> Dict:
        # User selected which phase has no actions (1, 2, 3, or 0 for "all have actions")
        # Returns same structure as calculate_capture_plan_from_save_state

        if phase_with_no_actions == 1:
            # Phase 1 has no actions (unusual but possible)
            plan = {
                "phases_to_capture": [1],
                "phase_modes": {1: "before_only"},
                "needs_red2_final": False,
                "export_mode": "simple",  # No save_state means simple export
            }

        elif phase_with_no_actions == 2:
            # Phase 2 has no actions → OCR Phase 1 fully + Phase 2 before only
            plan = {
                "phases_to_capture": [1, 2],
                "phase_modes": {1: "full", 2: "before_only"},
                "needs_red2_final": False,
                "export_mode": "simple",
            }

        elif phase_with_no_actions == 3:
            # Phase 3 has no actions → OCR Phase 1 & 2 fully + Phase 3 before only
            plan = {
                "phases_to_capture": [1, 2, 3],
                "phase_modes": {1: "full", 2: "full", 3: "before_only"},
                "needs_red2_final": False,
                "export_mode": "simple",
            }

        else:  # 0 or any other value means "All phases have actions"
            plan = {
                "phases_to_capture": [1, 2, 3],
                "phase_modes": {1: "full", 2: "full", 3: "full"},
                "needs_red2_final": True,
                "export_mode": "simple",
            }

        logging.info(f"Capture plan from user selection (no actions at phase {phase_with_no_actions}): {plan}")
        return plan
