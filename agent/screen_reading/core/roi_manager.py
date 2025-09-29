# ROI management for creating, updating, storing and loading ROIs
import json
import os
from typing import Dict, Optional, List, Tuple
from core.models import ROIMeta


class ROIManager:  # Manages ROI CRUD operations, handling both single ROI templates and multi-ROI collections.
    def __init__(self):
        self.rois: Dict[str, ROIMeta] = {}

    def add_roi(self, name: str, roi_meta: ROIMeta) -> bool:  # Add or triggers update for ROI by name.
        if name in self.rois:
            return False
        self.rois[name] = roi_meta
        return True

    def update_roi(self, name: str, roi_meta: ROIMeta) -> bool:  # Update existing ROI.
        if name not in self.rois:
            return False
        self.rois[name] = roi_meta
        return True

    def upsert_roi(
        self, name: str, roi_meta: ROIMeta
    ) -> None:  # Add or update ROI (create if doesn't exist, update if exists)
        self.rois[name] = roi_meta

    def delete_roi(self, name: str) -> bool:  # Delete ROI by name.
        if name in self.rois:
            del self.rois[name]
            return True
        return False

    def get_roi(self, name: str) -> Optional[ROIMeta]:  # Get ROI by name
        return self.rois.get(name)

    def get_roi_names(self) -> List[str]:  # Get list of all ROI names
        return list(self.rois.keys())

    def clear_all(self) -> int:  # Clear all ROIs.
        count = len(self.rois)
        self.rois.clear()
        return count

    def get_count(self) -> int:  # Get total number of ROIs
        return len(self.rois)

    def rename_roi(self, old_name: str, new_name: str) -> bool:  # Rename ROI.
        if old_name not in self.rois or new_name in self.rois:
            return False

        roi_meta = self.rois[old_name]
        roi_meta.name = new_name  # Update the name in the metadata too
        self.rois[new_name] = roi_meta
        del self.rois[old_name]
        return True

    def save_to_file(self, file_path: str) -> bool:  # Save all ROIs to JSON file
        if not self.rois:
            return False

        try:
            data = {name: roi_meta.to_json() for name, roi_meta in self.rois.items()}
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    def load_from_file(self, file_path: str) -> Tuple[bool, str, int]:  # Load ROIs from JSON file.
        try:
            with open(file_path, "r") as f:
                raw_data = json.load(f)

            # Check format: single template or multi-ROI
            if "roi" in raw_data and "canonical_size" in raw_data:
                # Single template format
                roi_meta = ROIMeta.from_json(raw_data["roi"])
                roi_name = roi_meta.name
                self.rois = {roi_name: roi_meta}
                return True, f"Loaded template: {roi_name}", 1

            elif raw_data and all(isinstance(v, dict) and "name" in v for v in raw_data.values()):
                # Multi-ROI format (template with sub-ROIs)
                self.rois = {k: ROIMeta.from_json(v) for k, v in raw_data.items()}
                return (
                    True,
                    f"Loaded {len(self.rois)} ROIs from template",
                    len(self.rois),
                )

            else:
                return (
                    False,
                    "Invalid format. Expected template JSON or multi-ROI JSON.",
                    0,
                )

        except FileNotFoundError:
            return False, f"File not found: {file_path}", 0
        except json.JSONDecodeError:
            return False, "Invalid JSON format", 0
        except Exception as e:
            return False, f"Loading failed: {e}", 0

    def create_roi_from_bounds(  # Create new ROI from relative coordinates [0..1].
        self,
        name: str,
        x: float,
        y: float,
        w: float,
        h: float,
        notes: str = "",
        **kwargs,
    ) -> ROIMeta:
        roi_meta = ROIMeta(name=name, x=x, y=y, w=w, h=h, notes=notes, **kwargs)
        self.upsert_roi(name, roi_meta)
        return roi_meta


    def get_rois_by_filter(self, filter_func) -> Dict[str, ROIMeta]:  # Get ROIs that match filter function.
        return {name: roi for name, roi in self.rois.items() if filter_func(roi)}

    def export_roi_config(self) -> Dict:  # Export ROI configuration for external consumption
        roi_config = {}
        for name, roi in self.rois.items():
            roi_config[name] = {
                "bounds": [roi.x, roi.y, roi.w, roi.h],
                "ocr_scale": getattr(roi, "ocr_scale", 1.0),
                "padding": getattr(roi, "padding_pixels", 10),
                "preferred_method": getattr(roi, "preferred_method", "Auto-Select"),
                "char_filter": getattr(roi, "char_filter", ""),
                "filter_mode": getattr(roi, "filter_mode", "whitelist"),
                "expected_values": getattr(roi, "expected_values", ""),
                "pattern": getattr(roi, "pattern", ""),
            }
        return roi_config

    def __len__(self) -> int:  # Support len() function
        return len(self.rois)

    def __contains__(self, name: str) -> bool:  # Support 'name in manager' syntax
        return name in self.rois

    def __iter__(self):  # Support iteration over ROI names
        return iter(self.rois)

    def __getitem__(self, name: str) -> ROIMeta:  # Support manager[name] syntax
        return self.rois[name]
