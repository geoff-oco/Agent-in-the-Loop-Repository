#!/usr/bin/env python3
# Session-based output manager with clean folder structure

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image


class SessionOutputManager:  # Manages all output for a game session in a single session folder

    def __init__(self, base_output_dir: str = "output"):
        self.base_dir = Path(base_output_dir)
        self.session_dir: Optional[Path] = None
        self.game_state_dir: Optional[Path] = None
        self.ocr_captures_dir: Optional[Path] = None
        self.logs_dir: Optional[Path] = None
        self.log_file: Optional[Path] = None
        self.log_handler: Optional[logging.FileHandler] = None

        # Session metadata
        self.session_name: Optional[str] = None
        self.session_start = time.time()
        self.capture_count = 0
        self.json_exports = 0

    def init_session(
        self, session_name: Optional[str] = None
    ) -> str:  # Initialise a new session with all subdirectories

        # Generate session name if not provided
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_name = session_name or f"session_{timestamp}"

        # Create main session directory
        self.session_dir = self.base_dir / self.session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.game_state_dir = self.session_dir / "game_state"
        self.game_state_dir.mkdir(exist_ok=True)

        self.ocr_captures_dir = self.session_dir / "ocr_captures"
        self.ocr_captures_dir.mkdir(exist_ok=True)

        # Create phase subdirectories
        for phase_num in [1, 2, 3]:
            phase_dir = self.ocr_captures_dir / f"phase_{phase_num}"
            phase_dir.mkdir(exist_ok=True)

        self.logs_dir = self.session_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        # Setup logging
        self._setup_logging()

        print(f"Session initialised: {self.session_name}")
        print(f"Output directory: {self.session_dir}")

        # Test logging and log session start
        logging.info(f"Session started: {self.session_name}")
        logging.info(f"Output directory: {self.session_dir}")
        logging.info(f"Logging system initialized successfully")

        return self.session_name

    def _setup_logging(self) -> None:  # Configure logging to session log file

        # Create session log file
        self.log_file = self.logs_dir / "session.log"

        # Get root logger and set level
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)  # Ensure the logger level is set to INFO

        # Remove any existing file handlers
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
                logger.removeHandler(handler)

        # Create new file handler
        self.log_handler = logging.FileHandler(self.log_file)
        self.log_handler.setLevel(logging.INFO)  # Set handler level too
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        self.log_handler.setFormatter(formatter)

        # Add handler
        logger.addHandler(self.log_handler)

        # Ensure we have a console handler too
        has_console = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in logger.handlers
        )
        if not has_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)  # Set console handler level too
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    def save_capture(
        self, image: Image.Image, phase_num: int, roi_name: str
    ) -> Path:  # Save OCR capture image to phase folder

        if not self.ocr_captures_dir:
            raise ValueError("Session not initialised")

        # Get phase directory
        phase_dir = self.ocr_captures_dir / f"phase_{phase_num}"
        phase_dir.mkdir(exist_ok=True)

        # Save image
        filename = f"{roi_name}.png"
        filepath = phase_dir / filename
        image.save(filepath)

        self.capture_count += 1
        logging.debug(f"Saved OCR capture: phase_{phase_num}/{filename}")

        return filepath

    def export_state(self, game_data: Dict[str, Any]) -> Path:  # Export game state JSON to session folder

        if not self.game_state_dir:
            raise ValueError("Session not initialised")

        # Generate filename
        filename = "game_state.json"
        filepath = self.game_state_dir / filename

        # Write JSON
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(game_data, f, indent=2, ensure_ascii=False)

        self.json_exports += 1
        logging.info(f"Exported game state to: {filename}")
        print(f"Game state saved: {filepath}")

        return filepath

    def get_stats(self) -> Dict[str, Any]:  # Get statistics for current session

        duration = time.time() - self.session_start

        stats = {
            "session_name": self.session_name,
            "duration_seconds": round(duration, 2),
            "captures_saved": self.capture_count,
            "json_exports": self.json_exports,
            "output_directory": str(self.session_dir) if self.session_dir else None,
        }

        return stats

    def cleanup(self) -> None:  # Clean up session resources

        # Log final stats
        stats = self.get_stats()
        logging.info(f"Session stats: {json.dumps(stats, indent=2)}")

        # Close log handler
        if self.log_handler:
            self.log_handler.close()
            logger = logging.getLogger()
            logger.removeHandler(self.log_handler)
            self.log_handler = None

        print(f"Session ended: {self.session_name}")

    def get_phase_dir(self, phase_num: int) -> Path:  # Get the directory for a specific phase
        if not self.ocr_captures_dir:
            raise ValueError("Session not initialised")

        return self.ocr_captures_dir / f"phase_{phase_num}"


# Singleton instance
_session_manager_instance: Optional[SessionOutputManager] = None


def get_session_output_manager(
    base_dir: str = "output",
) -> SessionOutputManager:  # Get or create singleton session output manager
    global _session_manager_instance
    if _session_manager_instance is None:
        _session_manager_instance = SessionOutputManager(base_dir)
    return _session_manager_instance
