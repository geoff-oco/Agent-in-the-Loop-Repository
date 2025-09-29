# Core components for ROI management and validation
from .models import ROIMeta, OCRResult, ProcessingMethod, BatchOCRResult
from .roi_manager import ROIManager
from .validators import TextValidator, get_text_validator

__all__ = [
    "ROIMeta",
    "OCRResult",
    "ProcessingMethod",
    "BatchOCRResult",
    "ROIManager",
    "TextValidator",
    "get_text_validator",
]
