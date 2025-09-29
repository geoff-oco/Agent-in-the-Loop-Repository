# Data models for ROI management and OCR processing
from dataclasses import dataclass, asdict, field
from typing import Dict, Optional
from enum import Enum


class ProcessingMethod(Enum):  # OCR preprocessing methods
    ORIGINAL = "Original"
    ENHANCED = "Enhanced"
    BINARY = "Binary"
    GREY_BOOST = "Grey-Boost"
    INVERTED = "Inverted"
    AUTO_SELECT = "Auto-Select"


@dataclass
class OCRResult:  # Structured OCR result for consumption
    text: str
    confidence: float
    method_used: str
    rule_passed: bool
    rule_message: str
    processing_time_ms: float = 0.0


@dataclass
class ROIMeta:  # Region of Interest metadata with OCR settings
    name: str
    x: float  # relative [0..1]
    y: float  # relative [0..1]
    w: float  # relative [0..1]
    h: float  # relative [0..1]
    notes: str = ""
    char_filter: str = ""  # Characters for filtering (blacklist or whitelist)
    filter_mode: str = "whitelist"  # "whitelist" or "blacklist"
    # Validation fields
    expected_values: str = ""  # Comma-separated expected values (Blue,Red3,etc)
    pattern: str = ""  # Pattern like L:(number)H:(number)R:(number) or 103(letter)
    # OCR processing settings
    ocr_scale: float = 1.0  # Individual scaling factor for this ROI's OCR processing
    preferred_method: str = "Auto-Select"  # Preferred OCR preprocessing method
    padding_pixels: int = 10  # Padding in pixels for better OCR context
    # Engine selection settings (NEW)
    preferred_ocr_engine: str = "auto"  # auto|paddle_gpu|paddle_cpu|tesseract

    # Canvas items (managed at runtime, not serialised)
    rect_id: Optional[int] = None
    handle_ids: Dict[str, int] = field(default_factory=dict)

    def to_json(self) -> Dict:  # Convert to JSON-serialisable dictionary
        d = asdict(self)
        # Remove runtime UI elements
        d.pop("rect_id", None)
        d.pop("handle_ids", None)
        return d

    @staticmethod
    def from_json(d: Dict) -> "ROIMeta":  # Create ROIMeta from JSON dictionary with backward compatibility
        return ROIMeta(
            name=d["name"],
            x=d["x"],
            y=d["y"],
            w=d["w"],
            h=d["h"],
            notes=d.get("notes", ""),
            char_filter=d.get("char_filter", d.get("whitelist", "")),
            filter_mode=d.get("filter_mode", "whitelist"),
            expected_values=d.get("expected_values", ""),
            pattern=d.get("pattern", ""),
            ocr_scale=d.get("ocr_scale", 1.0),
            preferred_method=d.get("preferred_method", "Auto-Select"),
            padding_pixels=d.get("padding_pixels", 10),
            # New fields with backward compatibility defaults
            preferred_ocr_engine=d.get("preferred_ocr_engine", "auto"),
        )


@dataclass
class BatchOCRResult:  # Result from processing multiple ROIs
    results: Dict[str, OCRResult]
    total_processing_time_ms: float
    timestamp: float


