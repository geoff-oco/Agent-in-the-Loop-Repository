# Unified OCR engine selection interface
from enum import Enum
from typing import Optional, Tuple
from PIL import Image


class EngineType(Enum):  # Available OCR engine types
    AUTO = "auto"  # Automatically select best engine
    PADDLE_GPU = "paddle_gpu"  # PaddleOCR with GPU acceleration
    PADDLE_CPU = "paddle_cpu"  # PaddleOCR with CPU only
    TESSERACT = "tesseract"  # Tesseract OCR


class EngineSelector:  # Manages OCR engine selection based on ROI preferences and availability.

    def __init__(self):
        # Lazy import to avoid circular dependencies
        self._paddle_engine = None
        self._tesseract_engine = None
        self._engines_checked = False
        self._available_engines = {}

    def _check_available_engines(self):  # Check which engines are available on the system
        if self._engines_checked:
            return

        # Check PaddleOCR availability
        try:
            from ocr.paddle_engine import get_paddle_engine

            self._paddle_engine = get_paddle_engine()
            if self._paddle_engine.available:
                self._available_engines[EngineType.PADDLE_CPU] = True
                if self._paddle_engine.gpu_available:
                    self._available_engines[EngineType.PADDLE_GPU] = True
                    print("PaddleOCR GPU acceleration available")
                else:
                    print("PaddleOCR available (CPU only)")
        except Exception as e:
            print(f"PaddleOCR not available: {e}")

        # Check Tesseract availability
        try:
            from ocr.tesseract_engine import get_tesseract_engine

            self._tesseract_engine = get_tesseract_engine()
            if self._tesseract_engine.available:
                self._available_engines[EngineType.TESSERACT] = True
                print("Tesseract OCR available")
        except Exception as e:
            print(f"Tesseract not available: {e}")

        self._engines_checked = True

    def get_available_engines(self) -> list:  # Get list of available engine types
        self._check_available_engines()
        return [engine_type.value for engine_type in self._available_engines.keys()]

    def select_engine(self, roi_meta: Optional[object] = None, preference: Optional[str] = None) -> EngineType:
        # Select the best available engine based on ROI preferences and availability
        self._check_available_engines()

        # Use explicit preference if provided
        if preference:
            engine_type = self._parse_engine_preference(preference)
            if engine_type in self._available_engines:
                return engine_type

        # Check ROI metadata for preference
        if roi_meta and hasattr(roi_meta, "preferred_ocr_engine"):
            engine_type = self._parse_engine_preference(roi_meta.preferred_ocr_engine)
            if engine_type in self._available_engines:
                return engine_type

        # Auto-selection logic based on ROI characteristics
        if roi_meta:
            return self._auto_select_for_roi(roi_meta)

        # Default fallback order
        if EngineType.PADDLE_GPU in self._available_engines:
            return EngineType.PADDLE_GPU
        elif EngineType.PADDLE_CPU in self._available_engines:
            return EngineType.PADDLE_CPU
        elif EngineType.TESSERACT in self._available_engines:
            return EngineType.TESSERACT
        else:
            return EngineType.AUTO  # No engines available

    def _parse_engine_preference(self, preference: str) -> EngineType:  # Parse string preference to EngineType
        preference_map = {
            "auto": EngineType.AUTO,
            "auto-select": EngineType.AUTO,
            "paddle_gpu": EngineType.PADDLE_GPU,
            "paddleocr (gpu)": EngineType.PADDLE_GPU,
            "paddle_cpu": EngineType.PADDLE_CPU,
            "paddleocr (cpu)": EngineType.PADDLE_CPU,
            "tesseract": EngineType.TESSERACT,
        }
        return preference_map.get(preference.lower(), EngineType.AUTO)

    def _auto_select_for_roi(
        self, roi_meta: object
    ) -> EngineType:  # Intelligent engine selection based on ROI characteristics
        # Check if ROI has specific characteristics that favour certain engines

        # Single character detection - Tesseract excels here
        if hasattr(roi_meta, "pattern") and roi_meta.pattern:
            # Check for single character patterns (but not adjustment patterns)
            roi_name = getattr(roi_meta, "name", "")
            if "_adj" not in roi_name and roi_meta.pattern in ["(number)", "(letter)", "(text)"]:
                if EngineType.TESSERACT in self._available_engines:
                    return EngineType.TESSERACT

        # Check ROI size hints (if we had them)
        if hasattr(roi_meta, "w") and hasattr(roi_meta, "h"):
            # Very small ROIs might benefit from Tesseract's scaling
            if roi_meta.w < 0.05 and roi_meta.h < 0.05:  # Less than 5% of screen
                if EngineType.TESSERACT in self._available_engines:
                    return EngineType.TESSERACT

        # Default to best available for general text
        if EngineType.PADDLE_GPU in self._available_engines:
            return EngineType.PADDLE_GPU
        elif EngineType.PADDLE_CPU in self._available_engines:
            return EngineType.PADDLE_CPU
        else:
            return EngineType.TESSERACT

    def get_engine_instance(self, engine_type: EngineType):  # Get the actual engine instance
        self._check_available_engines()

        if engine_type == EngineType.PADDLE_GPU or engine_type == EngineType.PADDLE_CPU:
            return self._paddle_engine
        elif engine_type == EngineType.TESSERACT:
            return self._tesseract_engine
        else:
            # Auto mode - return first available
            if self._paddle_engine and self._paddle_engine.available:
                return self._paddle_engine
            elif self._tesseract_engine and self._tesseract_engine.available:
                return self._tesseract_engine
            return None

    def is_gpu_available(self) -> bool:  # Check if GPU acceleration is available
        self._check_available_engines()
        return EngineType.PADDLE_GPU in self._available_engines


# Global instance for easy access
_selector_instance: Optional[EngineSelector] = None


def get_engine_selector() -> EngineSelector:  # Get the global EngineSelector singleton instance
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = EngineSelector()
    return _selector_instance
