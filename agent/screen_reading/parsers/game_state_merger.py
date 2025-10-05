# Merge OCR-generated game state with RTSViewer save_state.json allocations
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from parsers.save_state_parser import SaveStateParser


class GameStateMerger:
    def __init__(self):
        self.parser = SaveStateParser()

    def merge(self, ocr_game_state_path: str, save_state_path: str, output_dir: str) -> Tuple[bool, str]:
        # Merge OCR game state with save_state allocations
        # Returns (success: bool, output_filename: str)
        try:
            # Load OCR game state
            ocr_data = self._load_json(ocr_game_state_path)
            if not ocr_data:
                raise Exception(f"Failed to load OCR game state: {ocr_game_state_path}")

            # Check if save_state.json exists
            if not os.path.exists(save_state_path):
                logging.info("No save state file found - falling back to simple export")
                return self._export_simple_state(ocr_data, output_dir)

            # Parse save state allocations
            actions_by_phase = self.parser.parse_save_state(save_state_path)

            if not actions_by_phase:
                logging.warning("Save state parsing returned no allocations - falling back to simple export")
                return self._export_simple_state(ocr_data, output_dir)

            # Transform phase structure (before→start, insert actions)
            transformed_phases = self._transform_phase_structure(ocr_data.get("phases", []), actions_by_phase)

            # Build enriched game state
            enriched_data = {
                "meta": self._add_timestamp(ocr_data.get("meta", {})),
                "phases": transformed_phases,
                "final_state": ocr_data.get("final_state", {}),
            }

            # Export enriched state
            output_filename = self._export_enriched_state(enriched_data, output_dir)

            # Clean up save state file
            self._cleanup_save_state(save_state_path)

            logging.info(f"Successfully merged save state with OCR data: {output_filename}")
            return True, output_filename

        except Exception as e:
            logging.error(f"Error during merge: {e}", exc_info=True)
            # Fall back to simple export on any error
            try:
                return self._export_simple_state(ocr_data, output_dir)
            except:
                return False, "merge_failed"

    def _load_json(self, file_path: str) -> Dict:
        # Load JSON file with error handling
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"Malformed JSON in {file_path}: {e}")
            return {}
        except Exception as e:
            logging.error(f"Error loading {file_path}: {e}")
            return {}

    def _transform_phase_structure(self, phases: List[Dict], actions_by_phase: Dict[int, List[Dict]]) -> List[Dict]:
        # Transform phases: rename "before"→"start", insert "actions" arrays
        transformed = []

        for phase in phases:
            phase_num = phase.get("phase")
            if not phase_num:
                logging.warning(f"Phase missing phase number, skipping: {phase}")
                continue

            # Get actions for this phase (empty list if none)
            phase_actions = actions_by_phase.get(phase_num, [])

            # Build transformed phase with correct key order: phase, start, actions, after
            transformed_phase = {
                "phase": phase_num,
                "start": phase.get("before", {}),  # Rename "before" to "start"
                "actions": phase_actions,  # Insert actions array
                "after": phase.get("after", {}),  # Keep "after" as-is
            }

            transformed.append(transformed_phase)

        return transformed

    def _add_timestamp(self, meta: Dict) -> Dict:
        # Rebuild meta with correct field order: timestamp FIRST, then ler (matches template)
        new_meta = {"timestamp": datetime.now().isoformat()}

        # Add ler if it exists
        if "ler" in meta:
            new_meta["ler"] = meta["ler"]

        return new_meta

    def _export_enriched_state(self, data: Dict, output_dir: str) -> str:
        # Export enriched game state as game_state.json
        output_path = Path(output_dir) / "game_state.json"

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logging.info(f"Exported enriched game state to: {output_path}")
            return str(output_path)

        except Exception as e:
            logging.error(f"Failed to export enriched state: {e}")
            raise

    def _export_simple_state(self, ocr_data: Dict, output_dir: str) -> Tuple[bool, str]:
        # Export OCR-only game state as simple_game_state.json (fallback)
        output_path = Path(output_dir) / "simple_game_state.json"

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(ocr_data, f, indent=2, ensure_ascii=False)

            logging.info(f"Exported simple game state to: {output_path}")
            return False, str(output_path)

        except Exception as e:
            logging.error(f"Failed to export simple state: {e}")
            raise

    def _cleanup_save_state(self, save_state_path: str):
        # Delete save_state.json after successful merge (non-critical if fails)
        try:
            os.remove(save_state_path)
            logging.info(f"Cleaned up save state file: {save_state_path}")
        except Exception as e:
            logging.warning(f"Could not delete save_state.json: {e} - Please remove manually")
