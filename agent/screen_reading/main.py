#!/usr/bin/env python3
"""Screen reading system entry point."""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to Python path to allow package imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from the package
from screen_reading.core import ScreenReadingOrchestrator

# Simple logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ScreenReadingApp:
    """Main screen reading application."""

    def __init__(self, debug: bool = False, config_path: str = "config"):
        self.debug = debug
        self.config_path = config_path
        self.orchestrator = None

    def setup_components(self) -> None:
        try:
            logger.info("Initializing screen reading components...")
            self.orchestrator = ScreenReadingOrchestrator(debug=self.debug, config_path=self.config_path)
            logger.info("Screen reading system ready")

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise

    def run(self):
        if not self.orchestrator:
            raise RuntimeError("Components not initialized. Call setup_components() first.")

        try:
            logger.info("Starting screen reading analysis")
            result = self.orchestrator.capture_and_analyze_all()

            if result.overall_success:
                logger.info("Screen reading completed successfully")
            else:
                logger.warning("Screen reading completed with issues")

            return result

        except Exception as e:
            logger.error(f"Screen reading analysis failed: {e}")
            raise

    def print_summary(self, result) -> None:
        try:
            self.orchestrator.print_summary(result)
        except Exception as e:
            logger.error(f"Failed to print summary: {e}")
            print(f"[ERROR] Summary generation failed: {e}")

    def save_outputs(self, result) -> None:
        try:
            self.orchestrator.save_results(result)
        except Exception as e:
            logger.error(f"Failed to save results: {e}")

    def get_system_info(self) -> dict:
        if not self.orchestrator:
            return {"status": "not_initialized"}

        return {
            "status": "initialized",
            "debug_mode": self.debug,
            "config_path": self.config_path,
        }


def setup_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="RTS Game Screen Reading - Modular OCR and State Extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run screen reading with default settings
  %(prog)s --debug                  # Debug mode with verbose output
  %(prog)s --config custom_config   # Use custom configuration directory
        """,
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug logging and verbose output")
    parser.add_argument("--config", default="config", help="Configuration directory path (default: config)")
    parser.add_argument("--info", action="store_true", help="Show system information only")

    return parser


def show_info():
    print("\n" + "=" * 60)
    print("RTS Game OCR Screen Reading System")
    print("=" * 60)
    print("\nModular Architecture:")
    print("  • Screen Capture: Window detection and image capture")
    print("  • OCR Processing: Tesseract-based text extraction")
    print("  • Template Matching: Action card detection")
    print("  • Game State Building: Structured data assembly")
    print("\nOutputs:")
    print("  • game_state.json - Clean structured game data")
    print("  • debug_rois.json - Detailed extraction information")
    print("  • roi_captures/ - ROI and processing screenshots")
    print("-" * 60)


def main() -> int:
    parser = setup_args()
    args = parser.parse_args()

    # Show system info if requested
    if args.info:
        show_info()
        return 0

    try:
        # Show info first
        show_info()

        # Create and setup application
        app = ScreenReadingApp(debug=args.debug, config_path=args.config)
        app.setup_components()

        # Show system info if debug mode
        if args.debug:
            sys_info = app.get_system_info()
            print(f"\nSystem Info: {sys_info}")

        # Run analysis
        result = app.run()

        # Display results
        app.print_summary(result)

        # Save outputs
        app.save_outputs(result)

        # Return appropriate exit code
        return 0 if result.overall_success else 1

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Exiting...")
        return 130  # Standard exit code for Ctrl+C
    except Exception as e:
        logger.error(f"Application failed: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
