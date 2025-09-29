# PaddleOCR engine management with singleton pattern and GPU support
from typing import Optional, Tuple, Dict, List
from PIL import Image
import numpy as np
import os
import sys
import logging
import warnings
import time

# Basic environment variables for PaddleOCR
os.environ["FLAGS_eager_delete_tensor_gb"] = "0.0"
os.environ["FLAGS_fraction_of_gpu_memory_to_use"] = "0.8"

# Import PaddleOCR with fallback handling
try:
    from paddleocr import PaddleOCR

    _paddle_available = True
except Exception as e:
    print(f"PaddleOCR import failed: {e}")
    _paddle_available = False


class PaddleEngine:  # Wrapper for PaddleOCR with lazy initialisation and GPU support.
    _instance: Optional["PaddleEngine"] = None
    _paddle_ocr_gpu: Optional[object] = None  # GPU instance
    _paddle_ocr_cpu: Optional[object] = None  # CPU instance
    _initialised_gpu: bool = False
    _initialised_cpu: bool = False
    _init_failed: bool = False
    _gpu_available: bool = False

    def __new__(cls) -> "PaddleEngine":
        # Singleton pattern - only one instance allowed
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialisation of singleton
        if hasattr(self, "_singleton_initialised"):
            return
        self._singleton_initialised = True

        # Initialize GPU availability on creation
        self._gpu_available = self._detect_gpu_availability()

    @property
    def available(self) -> bool:  # Check if PaddleOCR is available and can be initialised
        return _paddle_available and not self._init_failed

    @property
    def gpu_available(self) -> bool:  # Check if GPU acceleration is available
        return self._gpu_available

    def get_engine(self, prefer_gpu: bool = True) -> Optional[object]:  # Get PaddleOCR instance with GPU preference
        if not self.available:
            return None

        # Try GPU first if preferred and available
        if prefer_gpu and self._gpu_available:
            if not self._initialised_gpu and not self._init_failed:
                self._initialise_paddle_gpu()
            if self._paddle_ocr_gpu:
                return self._paddle_ocr_gpu

        # Fallback to CPU
        if not self._initialised_cpu and not self._init_failed:
            self._initialise_paddle_cpu()
        return self._paddle_ocr_cpu if not self._init_failed else None

    def _initialise_paddle_gpu(self) -> None:  # Initialise PaddleOCR GPU instance with error handling
        try:
            import paddle

            print("Initializing PaddleOCR GPU...")

            # Detect and verify GPU availability first
            self._gpu_available = self._detect_gpu_availability()
            if not self._gpu_available:
                return

            # Set GPU device
            paddle.device.set_device("gpu:0")

            # GPU-optimised configuration
            paddle_config = {
                "use_textline_orientation": False,
                "lang": "en",
            }

            # Initialize PaddleOCR
            self._paddle_ocr_gpu = PaddleOCR(**paddle_config)
            self._initialised_gpu = True
            print("PaddleOCR GPU ready!")

        except Exception as e:
            print(f"PaddleOCR GPU initialization failed: {e}")
            self._gpu_available = False
            self._paddle_ocr_gpu = None

    def _initialise_paddle_cpu(self) -> None:  # Initialise PaddleOCR CPU instance as fallback
        try:
            import paddle

            print("Initializing PaddleOCR CPU...")

            # Set CPU device
            paddle.device.set_device("cpu")

            paddle_config = {
                "use_textline_orientation": False,
                "lang": "en",
            }

            # Initialize PaddleOCR
            self._paddle_ocr_cpu = PaddleOCR(**paddle_config)
            self._initialised_cpu = True
            print("PaddleOCR CPU ready!")

        except Exception as e:
            print(f"PaddleOCR CPU initialization failed: {e}")
            self._init_failed = True
            self._paddle_ocr_cpu = None

    def _detect_gpu_availability(self) -> bool:  # Check if GPU acceleration is available with thorough testing
        try:
            # Try to import paddle and check GPU availability
            import paddle

            # Check if compiled with CUDA
            if not paddle.is_compiled_with_cuda():
                return False

            # Check if GPU devices available using updated API
            try:
                gpu_count = paddle.device.cuda.device_count()
            except AttributeError:
                # Fallback for older API
                try:
                    gpu_count = paddle.cuda.device_count()
                except AttributeError:
                    return False

            if gpu_count == 0:
                return False

            # Try to actually use GPU
            try:
                paddle.device.set_device("gpu:0")
                test_tensor = paddle.ones([1, 1])
                _ = test_tensor.numpy()
                self._gpu_available = True
                return True
            except AttributeError:
                # Fallback for older API
                try:
                    paddle.set_device("gpu:0")
                    test_tensor = paddle.ones([1, 1])
                    _ = test_tensor.numpy()
                    self._gpu_available = True
                    return True
                except Exception as gpu_test_error:
                    return False
            except Exception as gpu_test_error:
                return False

        except ImportError:
            return False
        except Exception as e:
            return False

    def recognise_text(  # Perform OCR with multi-scale testing for optimal accuracy (32-48px height range)
        self,
        image: Image.Image,
        whitelist: Optional[str] = None,
        blacklist: Optional[str] = None,
        prefer_gpu: bool = True,
        early_exit_enabled: bool = False,
        roi_meta: Optional[object] = None,
    ) -> Tuple[str, float, float]:
        start_time = time.time()

        paddle = self.get_engine(prefer_gpu=prefer_gpu)
        if paddle is None:
            return "(PaddleOCR not available)", 0.0, 1.0

        # Track which engine is being used
        engine_type = "GPU" if (prefer_gpu and self._gpu_available and paddle == self._paddle_ocr_gpu) else "CPU"

        # Initialize validator for early exit if enabled
        validator = None
        if early_exit_enabled and roi_meta:
            try:
                from core.validators import get_text_validator

                validator = get_text_validator()
            except ImportError:
                pass

        # Generate test scales targeting 32-48px height range
        test_scales = self._generate_optimal_scales(image)

        best_result = ("", 0.0)
        best_score = 0.0
        best_scale = 1.0

        for scale in test_scales:
            try:
                # Scale image if needed
                if abs(scale - 1.0) > 0.01:
                    new_width = int(image.width * scale)
                    new_height = int(image.height * scale)
                    scaled_image = image.resize((new_width, new_height), Image.NEAREST)
                else:
                    scaled_image = image

                # Convert PIL image to numpy array for PaddleOCR
                img_array = np.array(scaled_image.convert("RGB"))
                results = paddle.ocr(img_array)

                # Extract text and confidence from PaddleOCR results
                text, confidence = self._extract_paddle_results(results, whitelist, blacklist)

                if text and confidence > best_score:
                    best_result = (text, confidence)
                    best_score = confidence
                    best_scale = scale

                    # Early exit if confidence > 92% AND pattern validates (when enabled)
                    if early_exit_enabled and validator and confidence > 92.0:
                        rule_passed, _ = validator.validate_text(roi_meta, text, debug=False)
                        if rule_passed:
                            # Break (processor will handle debug output)
                            break

                    # Fallback early exit for very high confidence
                    if confidence > 95.0:
                        break

            except Exception as e:
                continue

        if best_result[0]:
            return best_result[0], best_result[1], best_scale
        else:
            return "(empty)", 0.0, 1.0

    def _generate_optimal_scales(self, image: Image.Image) -> List[float]:
        # Generate test scales targeting 32-48px height range for PaddleOCR
        current_height = image.height
        if current_height == 0:
            return [1.0]

        target_heights = [32, 36, 40, 44, 48]
        scales = []

        for target_height in target_heights:
            scale = target_height / current_height
            if 0.1 <= scale <= 5.0:
                scales.append(scale)

        # Always include 1.0 (original) as fallback
        if 1.0 not in scales:
            scales.append(1.0)

        # Sort scales to test most likely optimal first
        scales.sort(key=lambda s: abs(s * current_height - 40))
        return scales

    def _extract_paddle_results(self, results, whitelist: Optional[str], blacklist: Optional[str]) -> Tuple[str, float]:
        # Extract text and confidence from PaddleOCR results
        if isinstance(results, list) and results:
            result_data = results[0]

            # Handle new dictionary format (PaddleOCR returns OCRResult objects)
            if isinstance(result_data, dict) or hasattr(result_data, "rec_texts"):
                if isinstance(result_data, dict):
                    rec_texts = result_data.get("rec_texts", [])
                    rec_scores = result_data.get("rec_scores", [])
                else:
                    rec_texts = getattr(result_data, "rec_texts", [])
                    rec_scores = getattr(result_data, "rec_scores", [])

                texts, confidences = [], []
                for text, score in zip(rec_texts, rec_scores):
                    filtered_text = self._apply_character_filter(text, whitelist, blacklist)
                    if filtered_text.strip():
                        texts.append(filtered_text)
                        confidences.append(float(score * 100 if score <= 1.0 else score))

                if texts:
                    combined_text = " ".join(texts)
                    average_confidence = sum(confidences) / len(confidences)
                    return combined_text, average_confidence

        return "", 0.0

    def _apply_character_filter(self, text: str, whitelist: Optional[str], blacklist: Optional[str]) -> str:
        if whitelist:
            text = "".join(char for char in text if char in whitelist)

        if blacklist:
            text = "".join(char for char in text if char not in blacklist)

        return text


# Global instance for easy access
_engine_instance: Optional[PaddleEngine] = None


def get_paddle_engine() -> PaddleEngine:  # Get the global PaddleEngine instance
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = PaddleEngine()
    return _engine_instance
