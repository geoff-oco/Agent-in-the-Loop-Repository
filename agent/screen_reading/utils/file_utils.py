"""File operations and utilities for the screen reading system."""

import json
import os
import glob
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class FileUtils:
    """File operations and utilities."""

    @staticmethod
    def save_json(data: Dict[str, Any], filepath: str, indent: int = 2) -> bool:
        """Save dictionary to JSON file."""
        try:
            dir_path = os.path.dirname(filepath)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, default=str)

            logger.debug(f"Saved JSON data to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save JSON to {filepath}: {e}")
            return False

    @staticmethod
    def ensure_directory_exists(dirpath: str) -> bool:
        """Create directory if it doesn't exist."""
        try:
            if not os.path.exists(dirpath):
                os.makedirs(dirpath, exist_ok=True)
                logger.debug(f"Created directory: {dirpath}")
            return True

        except Exception as e:
            logger.error(f"Failed to create directory {dirpath}: {e}")
            return False

    @staticmethod
    def cleanup_old_files(directory: str, pattern: str = "*.png", max_age_hours: int = 24) -> int:
        """Clean up old files matching pattern."""
        if not os.path.exists(directory):
            return 0

        try:
            import time

            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            files = glob.glob(os.path.join(directory, pattern))
            deleted_count = 0

            for file_path in files:
                try:
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"Deleted old file: {file_path}")
                except OSError as e:
                    logger.warning(f"Could not delete file {file_path}: {e}")

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old files from {directory}")

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup files in {directory}: {e}")
            return 0

    @staticmethod
    def list_files(directory: str, extension: str = None) -> List[str]:
        """List files in directory with optional extension filter."""
        try:
            if not os.path.exists(directory):
                return []

            files = []
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath):
                    if extension is None or filename.lower().endswith(extension.lower()):
                        files.append(filepath)

            return sorted(files)

        except Exception as e:
            logger.error(f"Failed to list files in {directory}: {e}")
            return []

    @staticmethod
    def get_directory_size(directory: str) -> int:
        """Calculate total directory size."""
        try:
            total_size = 0

            if not os.path.exists(directory):
                return 0

            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except OSError:
                        continue

            return total_size

        except Exception as e:
            logger.error(f"Failed to calculate directory size for {directory}: {e}")
            return 0

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {size_names[i]}"
