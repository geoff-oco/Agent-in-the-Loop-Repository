# OCR processing engines and pipelines
from .paddle_engine import PaddleEngine, get_paddle_engine
from .processor import OCRProcessor, get_ocr_processor

__all__ = [
    "PaddleEngine",
    "get_paddle_engine",
    "OCRProcessor",
    "get_ocr_processor",
]
