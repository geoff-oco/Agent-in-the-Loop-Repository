# Data models for live game reading
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class UnitCounts:  # Unit counts for a single faction

    L: int = 0
    H: int = 0
    R: int = 0

    def to_dict(self) -> Dict:
        return {"L": self.L, "H": self.H, "R": self.R}


@dataclass
class BaseUnits:  # Units at a base for both factions

    blue: UnitCounts = field(default_factory=UnitCounts)
    red: UnitCounts = field(default_factory=UnitCounts)

    def to_dict(self) -> Dict:
        return {"blue": self.blue.to_dict(), "red": self.red.to_dict()}


@dataclass
class PhaseData:  # Complete data for a single phase

    phase_number: int
    before: Dict[str, BaseUnits] = field(default_factory=dict)
    after: Dict[str, BaseUnits] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        # Always output full structure: before is always populated, after can be empty {} for before_only mode
        before_dict = {name: units.to_dict() for name, units in self.before.items()}
        after_dict = {name: units.to_dict() for name, units in self.after.items()} if self.after is not None else {}

        return {
            "phase": self.phase_number,
            "before": before_dict,
            "after": after_dict,
        }
