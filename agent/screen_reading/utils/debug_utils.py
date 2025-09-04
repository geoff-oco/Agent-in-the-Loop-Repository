"""Debug and analysis utilities for saving ROI captures and generating reports."""

import os
import time
import logging
from typing import Dict, Any, Optional

import cv2
import numpy as np

from .file_utils import FileUtils

logger = logging.getLogger(__name__)


class DebugUtils:
    """Debug and analysis utilities for ROI captures and processing reports."""

    def __init__(self, debug_dir: str = "roi_captures", auto_cleanup: bool = True):
        self.debug_dir = debug_dir
        self.auto_cleanup = auto_cleanup

        # Create debug directory
        FileUtils.ensure_directory_exists(self.debug_dir)

        # Clean up old files if enabled
        if self.auto_cleanup:
            self._cleanup_old_debug_files()

        logger.debug(f"DebugUtils initialized with directory: {debug_dir}")

    def save_debug_image(self, image: np.ndarray, filename: str, roi_name: str = None) -> Optional[str]:
        """Save debug image with timestamp."""
        try:
            # Build filename with timestamp
            timestamp = int(time.time())

            # Add roi_name if provided
            if roi_name:
                name_part, ext = os.path.splitext(filename)
                if not ext:
                    ext = ".png"
                debug_filename = f"{timestamp}_{name_part}_{roi_name}{ext}"
            else:
                name_part, ext = os.path.splitext(filename)
                if not ext:
                    ext = ".png"
                debug_filename = f"{timestamp}_{name_part}{ext}"

            debug_path = os.path.join(self.debug_dir, debug_filename)

            # Save image
            success = cv2.imwrite(debug_path, image)

            if success:
                logger.debug(f"Saved debug image: {debug_path}")
                return debug_path
            else:
                logger.warning(f"Failed to save debug image: {debug_path}")
                return None

        except Exception as e:
            logger.error(f"Failed to save debug image '{filename}': {e}")
            return None

    def save_results_summary(
        self, result_data: Dict[str, Any], filename: str = "processing_summary.json"
    ) -> Optional[str]:
        """Save processing results to JSON file."""
        try:
            # Add timestamp to result data
            result_data["debug_timestamp"] = time.time()
            result_data["debug_timestamp_readable"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # Save to debug directory
            output_path = os.path.join(self.debug_dir, filename)

            if FileUtils.save_json(result_data, output_path):
                logger.info(f"Saved results summary: {output_path}")
                return output_path
            else:
                return None

        except Exception as e:
            logger.error(f"Failed to save results summary: {e}")
            return None

    def save_detailed_debug(self, debug_data: Dict[str, Any], filename: str = "detailed_debug.json") -> Optional[str]:
        """Save detailed debug data to JSON file."""
        try:
            # Serialize data to handle numpy arrays and other non-JSON types
            serialized_data = self._serialize_debug_data(debug_data)

            # Add metadata
            serialized_data["debug_metadata"] = {
                "timestamp": time.time(),
                "timestamp_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
                "debug_dir": self.debug_dir,
                "data_keys": list(debug_data.keys()),
            }

            # Save to debug directory
            output_path = os.path.join(self.debug_dir, filename)

            if FileUtils.save_json(serialized_data, output_path):
                logger.info(f"Saved detailed debug info: {output_path}")
                return output_path
            else:
                return None

        except Exception as e:
            logger.error(f"Failed to save detailed debug info: {e}")
            return None

    def create_debug_report(self, processing_results: Dict[str, Any]) -> str:
        """Create human-readable debug report."""
        try:
            report_lines = []
            report_lines.append("=" * 60)
            report_lines.append("SCREEN READING DEBUG REPORT")
            report_lines.append("=" * 60)
            report_lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("")

            # System info
            if "system_info" in processing_results:
                report_lines.append("SYSTEM INFO:")
                for key, value in processing_results["system_info"].items():
                    report_lines.append(f"  {key}: {value}")
                report_lines.append("")

            # Processing statistics
            if "processing_stats" in processing_results:
                report_lines.append("PROCESSING STATISTICS:")
                stats = processing_results["processing_stats"]
                for key, value in stats.items():
                    report_lines.append(f"  {key}: {value}")
                report_lines.append("")

            # ROI results summary
            if "roi_results" in processing_results:
                report_lines.append("ROI PROCESSING RESULTS:")
                roi_results = processing_results["roi_results"]
                successful = sum(1 for r in roi_results.values() if r.get("success", False))
                total = len(roi_results)
                report_lines.append(f"  Success Rate: {successful}/{total} ({successful/total*100:.1f}%)")
                report_lines.append("")

                for roi_name, roi_result in roi_results.items():
                    success = "✓" if roi_result.get("success", False) else "✗"
                    conf = roi_result.get("confidence", 0)
                    report_lines.append(f"  {success} {roi_name}: {conf:.1f}% confidence")
                report_lines.append("")

            # Action cards summary
            if "action_cards" in processing_results:
                report_lines.append("ACTION CARDS:")
                cards_data = processing_results["action_cards"]
                if isinstance(cards_data, dict) and "phases" in cards_data:
                    phases = cards_data["phases"]
                    total_cards = sum(len(cards) for cards in phases.values())
                    report_lines.append(f"  Total Cards: {total_cards}")

                    for phase, cards in phases.items():
                        if cards:
                            report_lines.append(f"  Phase {phase}: {len(cards)} cards")
                            for i, card in enumerate(cards[:3], 1):  # Show first 3 cards
                                from_faction = getattr(card, "from_faction", "Unknown")
                                to_faction = getattr(card, "to_faction", "Unknown")
                                locked = "LOCKED" if getattr(card, "is_locked", False) else "UNLOCKED"
                                report_lines.append(f"    {i}. {from_faction} -> {to_faction} [{locked}]")
                            if len(cards) > 3:
                                report_lines.append(f"    ... and {len(cards) - 3} more")
                report_lines.append("")

            # Error summary
            if "errors" in processing_results:
                errors = processing_results["errors"]
                if errors:
                    report_lines.append("ERRORS:")
                    for error in errors[:5]:  # Show first 5 errors
                        report_lines.append(f"  • {error}")
                    if len(errors) > 5:
                        report_lines.append(f"  ... and {len(errors) - 5} more errors")
                    report_lines.append("")

            # Debug files info
            debug_files = FileUtils.list_files(self.debug_dir, ".png")
            if debug_files:
                report_lines.append(f"DEBUG FILES: {len(debug_files)} images saved to {self.debug_dir}")

                # Show directory size
                dir_size = FileUtils.get_directory_size(self.debug_dir)
                formatted_size = FileUtils.format_file_size(dir_size)
                report_lines.append(f"Debug directory size: {formatted_size}")
                report_lines.append("")

            report_lines.append("=" * 60)

            return "\n".join(report_lines)

        except Exception as e:
            logger.error(f"Failed to create debug report: {e}")
            return f"Debug report generation failed: {e}"

    def log_processing_time(self, operation_name: str, start_time: float) -> float:
        """Log and return operation duration."""
        try:
            duration = time.time() - start_time
            logger.info(f"{operation_name} completed in {duration:.2f}s")
            return duration
        except Exception:
            return 0.0

    def _cleanup_old_debug_files(self) -> None:
        try:
            # Clean up all existing PNG and JSON files on startup
            png_deleted = FileUtils.cleanup_old_files(self.debug_dir, "*.png", 0)
            json_deleted = FileUtils.cleanup_old_files(self.debug_dir, "*.json", 0)

            if png_deleted > 0 or json_deleted > 0:
                logger.info(f"Cleaned up {png_deleted} PNG files and {json_deleted} JSON files from {self.debug_dir}")

        except Exception as e:
            logger.warning(f"Debug file cleanup failed: {e}")

    def _serialize_debug_data(self, data: Any) -> Any:
        if isinstance(data, np.ndarray):
            return f"<numpy.ndarray: shape={data.shape}, dtype={data.dtype}>"
        elif isinstance(data, np.floating):
            return float(data)
        elif isinstance(data, np.integer):
            return int(data)
        elif isinstance(data, dict):
            return {k: self._serialize_debug_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_debug_data(item) for item in data]
        elif hasattr(data, "__dict__"):
            # Handle custom objects with attributes
            return {k: self._serialize_debug_data(v) for k, v in data.__dict__.items()}
        else:
            return data
