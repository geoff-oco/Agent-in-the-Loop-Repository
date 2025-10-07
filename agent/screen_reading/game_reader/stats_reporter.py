#!/usr/bin/env python3

from pathlib import Path
from typing import Dict, List, Tuple

from .models import PhaseData, BaseUnits


class StatsReporter:
    def __init__(self, stats_file: str = "output/stats.txt"):
        self.stats_file = Path(stats_file)
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)

    def update(self, phases: List[PhaseData], actions_by_phase: Dict = None):
        stats_text = self._format_stats(phases, actions_by_phase)
        self._write_file(stats_text)

    def _format_stats(
        self, phases: List[PhaseData], actions_by_phase: Dict = None
    ) -> str:
        lines = []
        lines.append("=== SIMULATION STATS ===\n")

        if not phases:
            lines.append("No data yet...")
            return "\n".join(lines)

        # Per-phase stats
        for phase in phases:
            lines.append(f"Phase {phase.phase_number}:")

            # Faction totals
            blue_total, red_total = self._calc_faction_totals(phase.before)
            lines.append(
                f"  Blue: {blue_total['L']}L {blue_total['H']}H {blue_total['R']}R"
            )
            lines.append(
                f"  Red:  {red_total['L']}L {red_total['H']}H {red_total['R']}R"
            )

            # Base control
            control = self._calc_base_control(phase.before)
            lines.append(f"  Bases: B:{control['blue']} R:{control['red']}")

            # Actions (if available)
            if actions_by_phase:
                action_count = len(actions_by_phase.get(phase.phase_number, []))
                lines.append(f"  Actions: {action_count}")

            lines.append("")

        # Summary
        total_actions = 0
        if actions_by_phase:
            total_actions = sum(
                len(actions_by_phase.get(p.phase_number, [])) for p in phases
            )

        lines.append(f"Total Phases: {len(phases)}")
        if actions_by_phase:
            lines.append(f"Total Actions: {total_actions}")

        return "\n".join(lines)

    def _calc_faction_totals(
        self, base_units_dict: Dict[str, BaseUnits]
    ) -> Tuple[Dict, Dict]:
        blue = {"L": 0, "H": 0, "R": 0}
        red = {"L": 0, "H": 0, "R": 0}

        for base_name, base_units in base_units_dict.items():
            blue["L"] += base_units.blue.L
            blue["H"] += base_units.blue.H
            blue["R"] += base_units.blue.R
            red["L"] += base_units.red.L
            red["H"] += base_units.red.H
            red["R"] += base_units.red.R

        return blue, red

    def _calc_base_control(self, base_units_dict: Dict[str, BaseUnits]) -> Dict:
        blue_bases = 0
        red_bases = 0

        for base_name, base_units in base_units_dict.items():
            blue_total = base_units.blue.L + base_units.blue.H + base_units.blue.R
            red_total = base_units.red.L + base_units.red.H + base_units.red.R

            if blue_total > red_total:
                blue_bases += 1
            elif red_total > blue_total:
                red_bases += 1

        return {"blue": blue_bases, "red": red_bases}

    def _write_file(self, content: str):
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    def clear(self):
        if self.stats_file.exists():
            try:
                self.stats_file.unlink()
            except Exception:
                pass
