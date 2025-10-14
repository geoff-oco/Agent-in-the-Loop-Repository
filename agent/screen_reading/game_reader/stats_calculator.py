#!/usr/bin/env python3

from typing import Dict, List, Optional, Any
from .models import PhaseData, BaseUnits


class StatsCalculator:
    def calculate_stats(
        self,
        phases: List[PhaseData],
        actions_by_phase: Optional[Dict[int, List]] = None,
        final_state: Optional[Dict[str, BaseUnits]] = None,
    ) -> Dict[str, Any]:
        # Calculate structured stats for all phases including combat results
        stats = {}

        for i, phase in enumerate(phases):
            phase_num = phase.phase_number
            phase_key = f"phase_{phase_num}"

            # Determine next phase start state (for units remaining/lost calculations)
            next_phase_start = None
            if i + 1 < len(phases):
                next_phase_start = phases[i + 1].before
            elif final_state:
                # Last phase uses final_state
                next_phase_start = final_state

            # Calculate blue stats
            blue_stats = self._calculate_faction_stats(phase, "blue", next_phase_start, actions_by_phase)

            # Calculate red stats
            red_stats = self._calculate_faction_stats(phase, "red", next_phase_start, actions_by_phase)

            stats[phase_key] = {"blue": blue_stats, "red": red_stats}

        return stats

    def _calculate_faction_stats(
        self,
        phase: PhaseData,
        faction: str,
        next_phase_start: Optional[Dict[str, BaseUnits]],
        actions_by_phase: Optional[Dict[int, List]],
    ) -> Dict[str, Any]:
        # Calculate stats for a single faction in a single phase
        phase_num = phase.phase_number

        # Units remaining after combat (use next phase start, or fallback to current phase after)
        if next_phase_start:
            units_remaining = self._count_faction_units(next_phase_start, faction)
        elif phase.after:
            # Fallback to current phase after state if no next phase
            units_remaining = self._count_faction_units(phase.after, faction)
        else:
            units_remaining = None

        # Units lost (current phase start - units remaining)
        current_start_units = self._count_faction_units(phase.before, faction)
        if units_remaining is not None:
            units_lost = max(0, current_start_units - units_remaining)  # Prevent negatives
        else:
            units_lost = None

        # Actions taken (only for blue, red is always null)
        # All actions in save_state belong to Blue (player actions only)
        if faction == "blue" and actions_by_phase:
            phase_actions = actions_by_phase.get(phase_num, [])
            actions_taken = len(phase_actions) if phase_actions else 0
        else:
            actions_taken = None

        # Bases controlled (use phase start state)
        bases_controlled_dict = self._count_bases_controlled(phase.before)
        bases_controlled = bases_controlled_dict.get(faction, 0)

        return {
            "units_remaining": units_remaining,
            "units_lost": units_lost,
            "actions_taken": actions_taken,
            "bases_controlled": bases_controlled,
        }

    def _count_faction_units(self, state_dict: Dict[str, BaseUnits], faction: str) -> int:
        # Sum all units (L+H+R) for a faction across all bases
        total = 0
        for base_name, base_units in state_dict.items():
            faction_units = base_units.blue if faction == "blue" else base_units.red
            total += faction_units.L + faction_units.H + faction_units.R
        return total

    def _count_bases_controlled(self, state_dict: Dict[str, BaseUnits]) -> Dict[str, int]:
        # Count bases where each faction has more total units than opponent
        blue_count = 0
        red_count = 0

        for base_name, base_units in state_dict.items():
            blue_total = base_units.blue.L + base_units.blue.H + base_units.blue.R
            red_total = base_units.red.L + base_units.red.H + base_units.red.R

            if blue_total > red_total:
                blue_count += 1
            elif red_total > blue_total:
                red_count += 1
            # Ties don't count for either faction

        return {"blue": blue_count, "red": red_count}
