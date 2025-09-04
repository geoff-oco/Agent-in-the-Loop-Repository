"""Game state building from processed ROI results."""

import logging
from typing import Dict, Any, Optional, List

from ..models import GameState, LER, Units, FactionUnits, Action

logger = logging.getLogger(__name__)


class GameStateBuilder:
    """Builds GameState objects from processed ROI results."""

    def __init__(self):
        logger.debug("GameStateBuilder initialized")

    def build_game_state(self, roi_results: Dict[str, Any]) -> Optional[GameState]:
        """Build GameState from ROI results."""
        try:
            logger.info("Building game state from ROI results")

            phase = self._extract_phase_from_results(roi_results)
            ler = self._extract_ler_from_results(roi_results)
            bases = self._extract_bases_from_results(roi_results)
            actions = self._extract_actions_from_results(roi_results)

            game_state = GameState(phase=phase, ler=ler, bases=bases, actions=actions)

            errors = game_state.validate_state()
            if errors:
                logger.warning(f"Game state validation warnings: {errors}")

            logger.info(
                f"Successfully built game state: Phase {phase}, {len(bases)} bases, "
                f"{game_state.total_actions} total actions"
            )
            return game_state

        except Exception as e:
            logger.error(f"Failed to build game state: {e}")
            return None

    def extract_phase_from_results(self, roi_results: Dict[str, Any]) -> int:
        return self._extract_phase_from_results(roi_results)

    def extract_ler_from_results(self, roi_results: Dict[str, Any]) -> LER:
        return self._extract_ler_from_results(roi_results)

    def extract_bases_from_results(self, roi_results: Dict[str, Any]) -> Dict[str, FactionUnits]:
        return self._extract_bases_from_results(roi_results)

    def extract_actions_from_results(self, roi_results: Dict[str, Any]) -> Optional[Dict[str, List[Action]]]:
        return self._extract_actions_from_results(roi_results)

    def _extract_phase_from_results(self, roi_results: Dict[str, Any]) -> int:
        if "phase_header" in roi_results and roi_results["phase_header"].success:
            phase = roi_results["phase_header"].extracted_data.get("phase", 0)
            logger.debug(f"Extracted phase: {phase}")
            return phase

        logger.warning("No valid phase found in results")
        return 0

    def _extract_ler_from_results(self, roi_results: Dict[str, Any]) -> LER:
        if "ler_panel" in roi_results and roi_results["ler_panel"].success:
            ler_data = roi_results["ler_panel"].extracted_data
            ler = LER(
                blue=ler_data.get("blue_ratio", 1.0),
                red=ler_data.get("red_ratio", 1.0),
                favour=ler_data.get("favour", "Blue"),
                raw=roi_results["ler_panel"].raw_text or "",
            )
            logger.debug(f"Extracted LER: {ler.blue}:{ler.red} favouring {ler.favour}")
            return ler

        logger.warning("No valid LER found in results, using default")
        return LER(blue=1.0, red=1.0, favour="Blue", raw="")

    def _extract_actions_from_results(self, roi_results: Dict[str, Any]) -> Optional[Dict[str, List[Action]]]:
        if "action_cards" not in roi_results or not roi_results["action_cards"].success:
            logger.info("No action cards found in results")
            return None

        action_phases = roi_results["action_cards"].extracted_data.get("phases", {})
        if not action_phases:
            logger.info("No action card phases found")
            return None

        actions = {"1": [], "2": [], "3": []}
        total_converted = 0

        for phase_str, action_cards in action_phases.items():
            for i, action_card in enumerate(action_cards, 1):
                try:
                    action = Action(
                        id=i,
                        **{"from": action_card.from_faction},  # Handle reserved keyword
                        to=action_card.to_faction,
                        L=action_card.light_count,
                        H=action_card.heavy_count,
                        R=action_card.ranged_count,
                        locked=action_card.is_locked,
                    )

                    target_phase = phase_str if phase_str in actions else "1"
                    actions[target_phase].append(action)
                    total_converted += 1

                    logger.debug(f"Converted action card: {action_card.from_faction} -> {action_card.to_faction}")

                except Exception as e:
                    logger.warning(f"Failed to convert action card to Action: {e}")

        logger.info(f"Converted {total_converted} action cards to actions across phases")
        return actions

    def _extract_bases_from_results(self, roi_results: Dict[str, Any]) -> Dict[str, FactionUnits]:
        bases = {}

        for base_prefix in ["blue", "red1", "red2", "red3"]:
            try:
                blue_units_key = f"{base_prefix}_blue_units"
                red_units_key = f"{base_prefix}_red_units"

                if (
                    blue_units_key in roi_results
                    and roi_results[blue_units_key].success
                    and red_units_key in roi_results
                    and roi_results[red_units_key].success
                ):

                    blue_units_crop = roi_results[blue_units_key].extracted_data.get("raw_crop")
                    red_units_crop = roi_results[red_units_key].extracted_data.get("raw_crop")

                    if blue_units_crop is not None and red_units_crop is not None:
                        blue_adj_cells = self._extract_adjustment_values(roi_results, base_prefix)

                        from ..processing import OCRProcessor

                        ocr_processor = OCRProcessor()

                        faction_units, confidence = ocr_processor.read_base_hybrid(
                            blue_units_crop, blue_adj_cells, red_units_crop, base_prefix
                        )

                        bases[base_prefix] = faction_units
                        logger.debug(f"Extracted {base_prefix} base units with confidence {confidence:.1f}")
                    else:
                        bases[base_prefix] = self._get_empty_faction_units()
                        logger.warning(f"Missing crop data for {base_prefix}")
                else:
                    bases[base_prefix] = self._get_empty_faction_units()
                    logger.warning(f"Missing units column data for {base_prefix}")

            except Exception as e:
                logger.error(f"Failed to extract base data for {base_prefix}: {e}")
                bases[base_prefix] = self._get_empty_faction_units()

        logger.info(f"Extracted {len(bases)} base configurations")
        return bases

    def _extract_adjustment_values(self, roi_results: Dict[str, Any], base_prefix: str) -> Dict[str, int]:
        blue_adj_cells = {}

        for unit_type in ["light", "heavy", "ranged"]:
            adj_key = f"{base_prefix}_blue_{unit_type}_adj"
            if adj_key in roi_results and roi_results[adj_key].success:
                value = roi_results[adj_key].extracted_data.get("value", 0)
                blue_adj_cells[unit_type] = value
                logger.debug(f"Found adjustment {adj_key}: {value}")

        return blue_adj_cells

    def _get_empty_faction_units(self) -> FactionUnits:
        empty_blue = Units(light=0, heavy=0, ranged=0)
        empty_red = Units(light=0, heavy=0, ranged=0)
        return FactionUnits(blue=empty_blue, red=empty_red)

    def create_empty_game_state(self) -> GameState:
        logger.info("Creating empty game state")
        return GameState.create_empty()

    def validate_game_state_components(self, roi_results: Dict[str, Any]) -> Dict[str, bool]:
        validation_results = {"phase_valid": False, "ler_valid": False, "bases_valid": False, "actions_valid": False}

        try:
            if "phase_header" in roi_results and roi_results["phase_header"].success:
                phase = roi_results["phase_header"].extracted_data.get("phase", 0)
                validation_results["phase_valid"] = 1 <= phase <= 3

            if "ler_panel" in roi_results and roi_results["ler_panel"].success:
                ler_data = roi_results["ler_panel"].extracted_data
                blue_ratio = ler_data.get("blue_ratio", 0)
                red_ratio = ler_data.get("red_ratio", 0)
                validation_results["ler_valid"] = blue_ratio > 0 and red_ratio > 0

            base_count = 0
            for base_prefix in ["blue", "red1", "red2", "red3"]:
                blue_key = f"{base_prefix}_blue_units"
                red_key = f"{base_prefix}_red_units"
                if (
                    blue_key in roi_results
                    and roi_results[blue_key].success
                    and red_key in roi_results
                    and roi_results[red_key].success
                ):
                    base_count += 1
            validation_results["bases_valid"] = base_count >= 2  # At least 2 bases should be valid

            if "action_cards" in roi_results and roi_results["action_cards"].success:
                action_data = roi_results["action_cards"].extracted_data
                total_cards = sum(len(cards) for cards in action_data.get("phases", {}).values())
                validation_results["actions_valid"] = total_cards > 0

            logger.debug(f"Component validation: {validation_results}")
            return validation_results

        except Exception as e:
            logger.error(f"Component validation failed: {e}")
            return validation_results
