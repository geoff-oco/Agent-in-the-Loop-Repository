# Parse RTSViewer save_state.json and transform allocations for game state export
import json
import logging
from pathlib import Path
from typing import Dict, List


class SaveStateParser:
    BASE_MAPPING = {0: "Blue", 1: "Red1", 2: "Red2", 3: "Red3"}  # Map From/To indices to base names

    @staticmethod
    def parse_save_state(save_state_path: str) -> Dict[int, List[Dict]]:
        # Parse save_state.json and extract allocations grouped by phase
        # Returns dictionary: {1: [...], 2: [...], 3: [...]} with sequential IDs
        try:
            save_state_file = Path(save_state_path)
            if not save_state_file.exists():
                logging.warning(f"Save state file not found: {save_state_path}")
                return {}

            with open(save_state_file, "r", encoding="utf-8") as f:
                save_state_data = json.load(f)

            allocations = save_state_data.get("Allocations", [])
            if not allocations:
                logging.warning("Save state contains no allocations")
                return {}

            # Filter to phases 1-3 only (OCR only captures 3 phases)
            valid_allocations = [a for a in allocations if 1 <= a.get("Phase", 0) <= 3]

            if len(valid_allocations) < len(allocations):
                filtered_count = len(allocations) - len(valid_allocations)
                logging.info(f"Filtered {filtered_count} allocations with invalid phases (only 1-3 allowed)")

            # Transform with sequential IDs and group by phase
            transformed = SaveStateParser._transform_allocations(valid_allocations)
            grouped = SaveStateParser._group_by_phase(transformed)

            logging.info(f"Parsed {len(valid_allocations)} allocations across {len(grouped)} phases")
            return grouped

        except json.JSONDecodeError as e:
            logging.error(f"Malformed save state JSON: {e}")
            return {}
        except Exception as e:
            logging.error(f"Error parsing save state: {e}", exc_info=True)
            return {}

    @staticmethod
    def _transform_allocations(allocations: List[Dict]) -> List[Dict]:
        # Transform allocations with sequential IDs and proper field names
        # IDs assigned sequentially across all phases (1, 2, 3... continuing)
        transformed = []
        sequential_id = 1

        # Sort by phase to maintain order, keep original order within each phase
        allocations_sorted = sorted(allocations, key=lambda x: x.get("Phase", 0))

        for allocation in allocations_sorted:
            try:
                # Validate required fields exist
                required_fields = ["Phase", "From", "To", "Light", "Heavy", "Ranged", "Locked"]
                if not all(field in allocation for field in required_fields):
                    logging.warning(f"Skipping allocation with missing fields: {allocation.get('Id', 'unknown')}")
                    continue

                # Validate From/To indices are valid
                from_idx = allocation["From"]
                to_idx = allocation["To"]
                if from_idx not in SaveStateParser.BASE_MAPPING or to_idx not in SaveStateParser.BASE_MAPPING:
                    logging.warning(f"Skipping allocation with invalid From/To: From={from_idx}, To={to_idx}")
                    continue

                # Transform to expected format
                transformed_allocation = {
                    "id": sequential_id,
                    "phase": allocation["Phase"],  # Keep phase for grouping
                    "from": SaveStateParser.BASE_MAPPING[from_idx],
                    "to": SaveStateParser.BASE_MAPPING[to_idx],
                    "L": allocation["Light"],
                    "H": allocation["Heavy"],
                    "R": allocation["Ranged"],
                    "locked": allocation["Locked"],  # Lowercase for consistency
                }

                transformed.append(transformed_allocation)
                sequential_id += 1

            except Exception as e:
                logging.warning(f"Error transforming allocation {allocation.get('Id', 'unknown')}: {e}")
                continue

        return transformed

    @staticmethod
    def _group_by_phase(allocations: List[Dict]) -> Dict[int, List[Dict]]:
        # Group transformed allocations by phase number, returns {1: [...], 2: [...], 3: [...]}
        grouped = {}

        for allocation in allocations:
            phase = allocation["phase"]

            # Remove phase field from allocation (not needed in final output)
            allocation_clean = {k: v for k, v in allocation.items() if k != "phase"}

            if phase not in grouped:
                grouped[phase] = []

            grouped[phase].append(allocation_clean)

        # Ensure all phases 1-3 exist (even if empty)
        for phase_num in [1, 2, 3]:
            if phase_num not in grouped:
                grouped[phase_num] = []

        return grouped
