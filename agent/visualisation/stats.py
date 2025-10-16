# Responsible for retrieving stats for display in the UI

import json
from pathlib import Path

# Get absolute path to stats.json relative to project root
# This file is in agent/visualisation/stats.py
# Project root is 2 levels up
PROJECT_ROOT = Path(__file__).parent.parent.parent
GAME_STATE_PATH = PROJECT_ROOT / "agent" / "decision_logic" / "run_agent" / "game_state" / "stats.json"


def stats_processing():
    """Process game stats from stats.json file.

    Returns:
        tuple: (total_phases, total_actions, phase_1_stats, phase_2_stats, phase_3_stats)
        None: If file not found or error occurs
    """
    try:
        if not GAME_STATE_PATH.exists():
            print(f"Stats file not found at: {GAME_STATE_PATH}")
            return None

        with open(GAME_STATE_PATH, mode="r", encoding="utf-8") as read_file:
            game_data = json.load(read_file)

        total_phases = game_data["summary"]["total_phases"]
        total_actions = game_data["summary"]["total_actions"]
        current_phase = ["", "", ""]

        for phase in range(total_phases):
            current_phase[phase] = _phase_processing(game_data, phase)

        return (total_phases, total_actions, (current_phase[0]), (current_phase[1]), (current_phase[2]))

    except FileNotFoundError:
        print(f"Stats file not found: {GAME_STATE_PATH}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding stats JSON: {e}")
        return None
    except KeyError as e:
        print(f"Missing key in stats data: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error processing stats: {e}")
        import traceback

        traceback.print_exc()
        return None


def _phase_processing(game_data, phase):
    """Process the data for each phase"""

    if phase == 0:
        ph = "phase_1"
    elif phase == 1:
        ph = "phase_2"
    elif phase == 2:
        ph = "phase_3"

    blue_units = game_data[ph]["blue"]["units_remaining"]
    blue_lost = game_data[ph]["blue"]["units_lost"]
    blue_bases = game_data[ph]["blue"]["bases_controlled"]
    blue_actions = game_data[ph]["blue"]["actions_taken"]

    red_units = game_data[ph]["red"]["units_remaining"]
    red_lost = game_data[ph]["red"]["units_lost"]
    red_bases = game_data[ph]["red"]["bases_controlled"]

    # Calculate differences (positive = blue advantage, negative = red advantage)
    diff_units = blue_units - red_units
    diff_lost = red_lost - blue_lost  # Positive = red lost more (blue advantage)
    diff_bases = blue_bases - red_bases

    return (
        (blue_units, blue_lost, blue_actions, blue_bases),
        (red_units, red_lost, "", red_bases),
        (diff_units, diff_lost, "", diff_bases),
    )


if __name__ == "__main__":
    pass
