#!/usr/bin/env python3

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class ProgressReporter:
    def __init__(self, progress_file: str = "output/progress.json"):
        self.progress_file = Path(progress_file)
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        self.phase_count = 3
        self.current_phase = 0

    def update(self, status: str, phase: Optional[int] = None, percentage: Optional[int] = None):
        if phase is not None:
            self.current_phase = phase

        # Calculate percentage if not provided
        if percentage is None and self.current_phase > 0:
            # Basic calculation: each phase is ~30%, plus initialisation and finalisation
            base_percentage = 10  # Initialisation
            phase_percentage = (self.current_phase - 1) * 30
            percentage = min(base_percentage + phase_percentage, 90)

        progress_data = {
            "status": status,
            "phase": self.current_phase,
            "percentage": percentage or 0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "complete": False,
        }

        try:
            with open(self.progress_file, "w") as f:
                json.dump(progress_data, f, indent=2)
        except Exception:
            pass  # Silently fail - don't break the main process

    def complete(self, status: str = "Screen reading complete!"):
        progress_data = {
            "status": status,
            "phase": self.phase_count,
            "percentage": 100,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "complete": True,
        }

        try:
            with open(self.progress_file, "w") as f:
                json.dump(progress_data, f, indent=2)
        except Exception:
            pass

    def error(self, error_message: str):
        progress_data = {
            "status": f"Error: {error_message}",
            "phase": self.current_phase,
            "percentage": -1,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "complete": False,
            "error": True,
        }

        try:
            with open(self.progress_file, "w") as f:
                json.dump(progress_data, f, indent=2)
        except Exception:
            pass

    def clear(self):
        if self.progress_file.exists():
            try:
                self.progress_file.unlink()
            except Exception:
                pass
