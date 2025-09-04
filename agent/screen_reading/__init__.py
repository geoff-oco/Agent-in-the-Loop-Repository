"""A modular reading system for RTS game analysis using OCR and template matching for ROI's (Regions of Interest)"""

__version__ = "2.0.0"
__author__ = "Refactored from original system"

# Import main components for easy access
from .core import ScreenReadingOrchestrator, GameStateBuilder
from .capture import ScreenCapture, WindowDetector
from .processing import OCRProcessor, ImagePreprocessor, ROIManager
from .template_matching import TemplateMatcher, ActionCardProcessor
from .utils import FileUtils, DebugUtils
from .models import GameState, LER, Units, FactionUnits, Action

__all__ = [
    "ScreenReadingOrchestrator",
    "GameStateBuilder",
    "ScreenCapture",
    "WindowDetector",
    "OCRProcessor",
    "ImagePreprocessor",
    "ROIManager",
    "TemplateMatcher",
    "ActionCardProcessor",
    "FileUtils",
    "DebugUtils",
    "GameState",
    "LER",
    "Units",
    "FactionUnits",
    "Action",
]
