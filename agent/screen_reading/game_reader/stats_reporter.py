#!/usr/bin/env python3

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import PhaseData, BaseUnits
from .stats_calculator import StatsCalculator


class StatsReporter:
    def __init__(self, stats_file: Path):
        self.stats_file = stats_file
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        self.calculator = StatsCalculator()

    def update(
        self,
        phases: List[PhaseData],
        actions_by_phase: Optional[Dict] = None,
        final_state: Optional[Dict[str, BaseUnits]] = None,
    ):
        stats_json = self._build_stats_json(phases, actions_by_phase, final_state)
        self._write_file(stats_json)

    def _build_stats_json(
        self,
        phases: List[PhaseData],
        actions_by_phase: Optional[Dict] = None,
        final_state: Optional[Dict[str, BaseUnits]] = None,
    ) -> Dict:
        # Build structured JSON stats using StatsCalculator
        if not phases:
            return {}

        return self.calculator.calculate_stats(phases, actions_by_phase, final_state)

    def _write_file(self, stats_dict: Dict):
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(stats_dict, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def clear(self):
        if self.stats_file.exists():
            try:
                self.stats_file.unlink()
            except Exception:
                pass
