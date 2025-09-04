"""Pydantic models for RTS game state: units, actions, and complete game data."""

from pydantic import BaseModel, Field
from typing import List, Dict, Literal, Optional
from datetime import datetime


class LER(BaseModel):
    """Loss Exchange Ratio - tactical advantage indicator (higher = better)."""

    blue: float = Field(ge=0.0, description="Blue force ratio value")
    red: float = Field(ge=0.0, description="Red force ratio value")
    favour: Literal["Blue", "Red"] = Field(description="Which side the ratio favours")
    raw: str = Field(default="", description="Raw OCR text for debugging")


class Units(BaseModel):
    """Unit counts: light(fast), heavy(durable), ranged(distance)."""

    light: int = Field(ge=0, le=100, description="Light unit count")
    heavy: int = Field(ge=0, le=100, description="Heavy unit count")
    ranged: int = Field(ge=0, le=100, description="Ranged unit count")

    @property
    def total(self) -> int:
        """Total unit count across all types."""
        return self.light + self.heavy + self.ranged


class FactionUnits(BaseModel):
    """Unit counts for both Blue and Red factions at a base."""

    blue: Units = Field(description="Blue faction units at this base")
    red: Units = Field(description="Red faction units at this base")

    @property
    def total_units(self) -> int:
        """Total units from both factions at this base."""
        return self.blue.total + self.red.total


class Action(BaseModel):
    """Planned action between bases with unit allocations."""

    id: int = Field(ge=1, description="Sequential ID within the phase (1, 2, 3, etc.)")
    from_: Literal["Blue", "Red1", "Red2", "Red3"] = Field(alias="from", description="Source base")
    to: Literal["Red1", "Red2", "Red3"] = Field(description="Target base")
    L: int = Field(ge=0, le=50, description="Light units assigned")
    H: int = Field(ge=0, le=50, description="Heavy units assigned")
    R: int = Field(ge=0, le=50, description="Ranged units assigned")
    locked: bool = Field(default=False, description="Whether action is locked from changes")

    def canonical_key(self) -> tuple:
        """Generate a unique key for deduplication."""
        return (self.from_, self.to, self.L, self.H, self.R)

    @property
    def total_units(self) -> int:
        """Total units involved in this action."""
        return self.L + self.H + self.R


class GameState(BaseModel):
    """Complete RTS game state: phase, units, actions, and LER."""

    timestamp: datetime = Field(default_factory=datetime.now, description="When state was captured")
    phase: int = Field(ge=0, le=3, description="Current game phase (1-3)")
    ler: LER = Field(description="Current Loss Exchange Ratio")
    bases: Dict[str, FactionUnits] = Field(description="Unit counts per base for both factions")
    actions: Optional[Dict[str, List[Action]]] = Field(default=None, description="Actions organized by phase")

    @classmethod
    def create_empty(cls) -> "GameState":
        """Create empty game state with all zeros."""
        empty_units = Units(light=0, heavy=0, ranged=0)
        empty_faction = FactionUnits(blue=empty_units, red=empty_units)

        return cls(
            phase=0,
            ler=LER(blue=1.0, red=1.0, favour="Blue", raw=""),
            bases={"blue": empty_faction, "red1": empty_faction, "red2": empty_faction, "red3": empty_faction},
            actions={"1": [], "2": [], "3": []},
        )

    def validate_state(self) -> List[str]:
        """Validate game state and return error messages (empty if valid)."""
        errors = []

        # Check phase range
        if self.phase < 1 or self.phase > 3:
            errors.append(f"Invalid phase: {self.phase} (must be 1-3)")

        # Check required bases exist
        required_bases = {"blue", "red1", "red2", "red3"}
        if not required_bases.issubset(self.bases.keys()):
            missing = required_bases - set(self.bases.keys())
            errors.append(f"Missing bases: {missing}")

        # Check LER values are positive
        if self.ler.blue <= 0 or self.ler.red <= 0:
            errors.append(f"Invalid LER values: blue={self.ler.blue}, red={self.ler.red}")

        return errors

    @property
    def total_actions(self) -> int:
        """Total number of actions across all phases."""
        if not self.actions:
            return 0
        return sum(len(actions) for actions in self.actions.values())

    @property
    def total_units_all_bases(self) -> int:
        """Total units across all bases and factions."""
        return sum(base.total_units for base in self.bases.values())
