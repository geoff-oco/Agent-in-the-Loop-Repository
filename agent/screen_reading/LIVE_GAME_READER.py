#!/usr/bin/env python3
# Live Game Reader - Template-based navigation with 3-phase processing

import os
import sys
import argparse
import warnings
import logging

# Suppress verbose logging
os.environ["GLOG_minloglevel"] = "2"
warnings.filterwarnings("ignore")
logging.getLogger("paddleocr").setLevel(logging.ERROR)


def main():
    parser = argparse.ArgumentParser(description="Live Game Reader - Template-based 3-phase processing")
    args = parser.parse_args()

    # Logging will be configured by SessionOutputManager when session is initialised

    # Import after environment setup
    from game_reader.game_reader import LiveGameReader

    # Create and run reader with default settings
    print("\n" + "=" * 60)
    print("LIVE GAME READER")
    print("=" * 60 + "\n")

    reader = LiveGameReader()

    # Run game reading
    try:
        success = reader.run()
        if success:
            print("\nSUCCESS: Game reading completed")
            sys.exit(0)
        else:
            print("\nFAILED: Game reading failed")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
