#!/usr/bin/env python3
# ==============================
# Modular Computer Vision (CV) & Optical Character Recognition (OCR) calibration tool with real-time ROI definition and OCR testing.

# Usage: python LIVE_ROI_STUDIO.py - This is the entry point for the tool.

# Modules:
# - core/: Data models, ROI management, validation
# - imaging/: Image processing, screen capture, utilities
# - ocr/: PaddleOCR engine, processing pipeline, real-time optimisation
# - ui/: User interface with dependency injection

# For agent integration, use:
#     from ocr import create_game_reader
#     reader = create_game_reader("path/to/rois.json")
#     game_state = reader.read_game_state()

# Author: Brody Orchard - 10582880
# ==============================

# Suppress verbose logging before any other imports
import os
import warnings
import logging

# Set environment variables to suppress PaddleOCR initialisation output
os.environ["GLOG_minloglevel"] = "2"  # Suppress INFO and WARNING logs
os.environ["FLAGS_eager_delete_tensor_gb"] = "0.0"
os.environ["FLAGS_fraction_of_gpu_memory_to_use"] = "0.8"

# Configure logging to suppress warnings
logging.getLogger("paddleocr").setLevel(logging.ERROR)
logging.getLogger("paddle").setLevel(logging.ERROR)
logging.getLogger("ppocr").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

# Import the modular ROI Studio
from roi_studio import main

if __name__ == "__main__":
    main()
