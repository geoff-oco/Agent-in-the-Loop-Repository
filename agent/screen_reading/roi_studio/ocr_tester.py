# OCR testing and preview functionality
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import time
from typing import Optional, Callable

from core import ROIMeta, ROIManager
from imaging import ImageUtils
from ocr import get_ocr_processor
from ocr.engine_selector import get_engine_selector
from .ui_components import UIConfig, UIHelpers


class OCRTester:  # Handles OCR testing, preview and results display
    def __init__(
        self,
        roi_manager: ROIManager,
        get_current_frame: Callable[[], Optional[Image.Image]],
        get_frozen_frame: Callable[[], Optional[Image.Image]],
        get_selected_roi: Callable[[], Optional[str]],
        status_callback: Callable[[str], None],
        accepted_chars_var: tk.StringVar,
        padding_var: tk.IntVar,
        early_exit_var: tk.BooleanVar,
        preferred_method_var: tk.StringVar,
        ocr_engine_var: tk.StringVar,
        expected_entry: ttk.Entry,
        pattern_entry: ttk.Entry,
        char_filter_entry: ttk.Entry,
        filter_mode_var: tk.StringVar,
    ):
        self.roi_manager = roi_manager
        self.get_current_frame = get_current_frame
        self.get_frozen_frame = get_frozen_frame
        self.get_selected_roi = get_selected_roi
        self.status_callback = status_callback
        self.accepted_chars_var = accepted_chars_var
        self.padding_var = padding_var
        self.early_exit_var = early_exit_var
        self.preferred_method_var = preferred_method_var
        self.ocr_engine_var = ocr_engine_var
        self.expected_entry = expected_entry
        self.pattern_entry = pattern_entry
        self.char_filter_entry = char_filter_entry
        self.filter_mode_var = filter_mode_var

        # OCR components
        self.ocr_processor = get_ocr_processor()
        self.engine_selector = get_engine_selector()

        # UI components (will be set by parent)
        self.preview_notebook: Optional[ttk.Notebook] = None

        # Engine options
        self.engine_options = []
        self._update_engine_options()

    def create_preview_section(self, parent: tk.Widget) -> None:
        # Create the live preview & testing section
        preview_frame = ttk.LabelFrame(parent, text="Live Preview & Testing")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Preview buttons
        btn_row = ttk.Frame(preview_frame)
        btn_row.pack(fill=tk.X, padx=8, pady=4)

        ttk.Button(btn_row, text="Preview Image", command=self.preview_image_only).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Test Individual ROI", command=self.test_roi_ocr).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Test All ROIs", command=self.test_all_rois).pack(side=tk.LEFT, padx=2)

        # Early exit toggle next to Test All ROIs button
        chk_early_exit = ttk.Checkbutton(btn_row, text="Early Exit (90%+)", variable=self.early_exit_var)
        chk_early_exit.pack(side=tk.LEFT, padx=8)

        # Preview notebook for multiple tabs
        self.preview_notebook = ttk.Notebook(preview_frame)
        self.preview_notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def preview_image_only(self) -> None:
        # Show cropped ROI image without OCR
        selected_name = self.get_selected_roi()
        if not selected_name or selected_name not in self.roi_manager:
            return

        frame = self.get_frozen_frame() or self.get_current_frame()
        if not frame:
            messagebox.showwarning("Preview", "No image available")
            return

        roi = self.roi_manager[selected_name]

        # Crop ROI with current padding
        roi_image = ImageUtils.crop_roi(frame, roi, self.padding_var.get())
        if not roi_image:
            return

        # OCR engines now handle scaling internally
        scaled_roi_image = roi_image

        # Clear and show just the scaled image
        for widget in self.preview_notebook.winfo_children():
            widget.destroy()

        # Create single tab for preview image
        tab = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(tab, text="Preview")

        # Display image
        try:
            # Scale image for display
            display_size = (300, 200)
            display_img = scaled_roi_image.copy()
            display_img.thumbnail(display_size, Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(display_img)
            label = ttk.Label(tab, image=photo)
            label.image = photo  # Keep reference
            label.pack(pady=10)

            # Show image info (no OCR scale since it's just a preview)
            info_text = f"Size: {scaled_roi_image.width}x{scaled_roi_image.height}"
            ttk.Label(tab, text=info_text).pack()

        except Exception as e:
            ttk.Label(tab, text=f"Error: {e}").pack()

    def test_roi_ocr(self) -> None:
        # Test OCR on selected ROI with all methods
        selected_name = self.get_selected_roi()
        if not selected_name or selected_name not in self.roi_manager:
            messagebox.showwarning("Test OCR", "Select an ROI first")
            return

        frame = self.get_frozen_frame() or self.get_current_frame()
        if not frame:
            messagebox.showwarning("Test OCR", "No image available")
            return

        roi = self.roi_manager[selected_name]

        # Crop ROI
        roi_image = ImageUtils.crop_roi(frame, roi, self.padding_var.get())
        if not roi_image:
            return

        try:
            # Create test ROI with current UI settings
            test_roi = self._create_test_roi_from_ui_settings(roi)

            # Clear previous results
            for widget in self.preview_notebook.winfo_children():
                widget.destroy()

            # Process with multi-engine OCR
            results = self.ocr_processor.process_multi_engine(
                roi_image,
                test_roi,
                accepted_chars=self.accepted_chars_var.get(),
                early_exit_enabled=self.early_exit_var.get(),
            )

            # Create result tabs
            for combined_name, processed_img, text, confidence, rule_passed, rule_message in results:
                self._create_ocr_result_tab(
                    combined_name, processed_img, text, confidence, rule_passed, rule_message, test_roi
                )

            self.status_callback(f"OCR completed for '{selected_name}'")

        except Exception as e:
            messagebox.showerror("OCR Error", f"OCR processing failed: {e}")

    def test_all_rois(self) -> None:
        # Test OCR on all defined ROIs
        if len(self.roi_manager) == 0:
            messagebox.showwarning("Test All ROIs", "No ROIs defined")
            return

        frame = self.get_frozen_frame() or self.get_current_frame()
        if not frame:
            messagebox.showwarning("Test All ROIs", "No image available")
            return

        # Start performance tracking
        overall_start_time = time.time()
        total_rois = len(self.roi_manager.get_roi_names())
        rois_with_early_exit = 0

        print(f"\n=== Starting Test All ROIs ===")
        print(f"Early exit enabled: {self.early_exit_var.get()}")
        print(f"Total ROIs to process: {total_rois}")

        # Create results window
        results_window = self._create_results_window()

        # Process all ROIs
        for roi_name in self.roi_manager.get_roi_names():
            roi = self.roi_manager[roi_name]
            early_exit_triggered, processing_error = self._process_single_roi_for_test(
                roi_name, roi, frame, results_window.scrollable_frame
            )
            if early_exit_triggered:
                rois_with_early_exit += 1

        # Display performance summary
        total_time = (time.time() - overall_start_time) * 1000
        print(f"\n=== Test All ROIs Performance Summary ===")
        print(f"Total processing time: {total_time:.1f}ms ({total_time/1000:.2f}s)")
        print(f"Total ROIs processed: {total_rois}")
        print(f"ROIs with early exit: {rois_with_early_exit} ({rois_with_early_exit/total_rois*100:.1f}%)")
        print(f"Average time per ROI: {total_time/total_rois:.1f}ms")
        print("=" * 50)

        self.status_callback(
            f"Tested {len(self.roi_manager)} ROIs in {total_time/1000:.2f}s"
            + (f" ({rois_with_early_exit} early exits)" if rois_with_early_exit > 0 else "")
        )

    def _create_test_roi_from_ui_settings(self, roi: ROIMeta) -> ROIMeta:
        # Create ROI with current UI settings for testing
        return ROIMeta(
            name=roi.name,
            x=roi.x,
            y=roi.y,
            w=roi.w,
            h=roi.h,
            notes=roi.notes,
            expected_values=self.expected_entry.get(),
            pattern=self.pattern_entry.get(),
            char_filter=self.char_filter_entry.get(),
            filter_mode=self.filter_mode_var.get(),
            padding_pixels=self.padding_var.get(),
            preferred_method=self.preferred_method_var.get(),
        )

    def _create_ocr_result_tab(
        self,
        combined_name: str,
        processed_img: Image.Image,
        text: str,
        confidence: float,
        rule_passed: bool,
        rule_message: str,
        test_roi: ROIMeta,
    ) -> None:
        # Create a single result tab for OCR testing
        tab = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(tab, text=combined_name)

        try:
            # Extract engine info from combined name
            if "-" in combined_name:
                engine_name, method_name = combined_name.split("-", 1)
            else:
                engine_name, method_name = combined_name, "Unknown"

            # Create display image
            display_img = UIHelpers.create_thumbnail_image(processed_img)

            # Image display
            img_label = ttk.Label(tab, image=display_img)
            img_label.image = display_img  # Keep reference
            img_label.pack(pady=5)

            # Results display using UIHelpers
            UIHelpers.create_result_display(tab, text, confidence, rule_passed, rule_message)

            # Engine and method info
            engine_info = f"Engine: {engine_name} | Method: {method_name}"
            UIHelpers.create_info_label(tab, engine_info).pack(anchor=tk.W, pady=2)

            # Image size info
            size_info = f"Processed size: {processed_img.width}x{processed_img.height}"
            UIHelpers.create_info_label(tab, size_info).pack(anchor=tk.W)

        except Exception as e:
            ttk.Label(tab, text=f"Display error: {e}").pack()

    def _create_results_window(self):
        # Create scrollable results window for test all ROIs
        from tkinter import Toplevel

        class ScrollableFrame:
            def __init__(self, parent):
                self.parent = parent
                self.canvas = tk.Canvas(parent)
                self.scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.canvas.yview)
                self.scrollable_frame = ttk.Frame(self.canvas)
                self._destroyed = False

                self.scrollable_frame.bind(
                    "<Configure>",
                    lambda e: (
                        self.canvas.configure(scrollregion=self.canvas.bbox("all")) if not self._destroyed else None
                    ),
                )

                self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
                self.canvas.configure(yscrollcommand=self.scrollbar.set)

                # Bind mouse wheel events for scrolling
                self._bind_mousewheel()

                # Bind cleanup when parent window is destroyed
                self.parent.bind("<Destroy>", self._on_window_destroy)

                self.canvas.pack(side="left", fill="both", expand=True)
                self.scrollbar.pack(side="right", fill="y")

            def _on_window_destroy(self, event):
                # Only cleanup if the destroyed widget is our parent window
                if event.widget == self.parent:
                    self._destroyed = True
                    # Unbind mouse wheel events
                    try:
                        self.canvas.unbind_all("<MouseWheel>")
                    except:
                        pass

            def _bind_mousewheel(self):
                # Windows mouse wheel binding
                def _on_mousewheel(event):
                    # Safety check: don't process if canvas is destroyed
                    if self._destroyed or not self.canvas.winfo_exists():
                        return

                    try:
                        # Windows mouse wheel scrolling
                        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    except tk.TclError:
                        # Canvas no longer exists, mark as destroyed
                        self._destroyed = True

                # Bind Windows mouse wheel event
                self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        results_window = Toplevel()
        results_window.title("Test All ROIs Results")
        results_window.geometry("800x600")

        results_window.scrollable_frame = ScrollableFrame(results_window).scrollable_frame

        return results_window

    def _process_single_roi_for_test(self, roi_name: str, roi: ROIMeta, frame: Image.Image, parent_frame: tk.Widget):
        # Process a single ROI for test all functionality
        early_exit_triggered = False
        processing_error = False

        try:
            # Create test ROI with UI settings
            test_roi = self._create_test_roi_from_ui_settings(roi)

            # Crop ROI - this is just the base image for OCR processing
            roi_image = ImageUtils.crop_roi(frame, roi, roi.padding_pixels or 0)
            if not roi_image:
                return early_exit_triggered, True

            # Create frame for this ROI's results
            roi_frame = ttk.LabelFrame(parent_frame, text=f"ROI: {roi_name}")
            roi_frame.pack(fill=tk.X, padx=5, pady=5)

            # Process with OCR
            early_exit_enabled = self.early_exit_var.get()
            print(f"Processing {roi_name} with early_exit={early_exit_enabled}")  # Debug logging

            results = self.ocr_processor.process_multi_engine(
                roi_image,
                test_roi,
                accepted_chars=self.accepted_chars_var.get(),
                early_exit_enabled=early_exit_enabled,
            )

            # Display results based on early exit setting
            if results:
                if early_exit_enabled:
                    # Early exit ON: Show only best result (compact display)
                    sorted_results = sorted(
                        results,
                        key=lambda r: (r[4], r[3]),  # r[4] is rule_passed (bool), r[3] is confidence
                        reverse=True,
                    )
                    best_result = sorted_results[0]
                    combined_name, processed_img, text, confidence, rule_passed, rule_message = best_result

                    # Check if early exit was triggered (confidence > 90%)
                    if confidence > 90.0:
                        early_exit_triggered = True

                    # Create compact result display
                    result_frame = ttk.Frame(roi_frame)
                    result_frame.pack(fill=tk.X, padx=5, pady=5)

                    # Thumbnail image
                    display_img = UIHelpers.create_thumbnail_image(processed_img, (60, 40))
                    img_label = ttk.Label(result_frame, image=display_img)
                    img_label.image = display_img
                    img_label.pack(side=tk.LEFT, padx=5)

                    # Result info
                    info_frame = ttk.Frame(result_frame)
                    info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

                    UIHelpers.create_result_display(info_frame, text, confidence, rule_passed, rule_message)

                    # Engine info
                    engine_info = f"Best: {combined_name}"
                    UIHelpers.create_info_label(info_frame, engine_info).pack(anchor=tk.W)

                else:
                    # Early exit OFF: Show all results grouped by engine (row-based layout)
                    # Group results by OCR engine type (not processing method)
                    engine_groups = {}

                    for result in results:
                        combined_name, processed_img, text, confidence, rule_passed, rule_message = result

                        # Parse correctly: format is "ProcessingMethod-OCREngine"
                        if "-" in combined_name:
                            method_name, engine_name = combined_name.split("-", 1)
                        else:
                            method_name = "Unknown"
                            engine_name = combined_name

                        # Normalize engine names for cleaner display
                        if "PaddleOCR" in engine_name:
                            engine_name = "PADDLEOCR"
                        elif "Tesseract" in engine_name:
                            engine_name = "TESSERACT"

                        if engine_name not in engine_groups:
                            engine_groups[engine_name] = []
                        engine_groups[engine_name].append((result, method_name))

                    # Display each engine group as a row (ensure consistent ordering)
                    engine_order = ["TESSERACT", "PADDLEOCR"]  # Preferred order
                    ordered_engines = [eng for eng in engine_order if eng in engine_groups]
                    ordered_engines.extend([eng for eng in engine_groups.keys() if eng not in engine_order])

                    for engine_name in ordered_engines:
                        engine_data = engine_groups[engine_name]

                        # Engine row header
                        engine_header = ttk.LabelFrame(roi_frame, text=f"{engine_name} Results")
                        engine_header.pack(fill=tk.X, padx=5, pady=2)

                        # Horizontal container for all methods of this engine
                        engine_row = ttk.Frame(engine_header)
                        engine_row.pack(fill=tk.X, padx=3, pady=3)

                        # Display each method result side by side
                        for i, (result, method_name) in enumerate(engine_data):
                            combined_name, processed_img, text, confidence, rule_passed, rule_message = result

                            # Individual method frame (side by side)
                            method_frame = ttk.Frame(engine_row)
                            method_frame.pack(side=tk.LEFT, fill=tk.Y, padx=3)

                            # Thumbnail image
                            display_img = UIHelpers.create_thumbnail_image(processed_img, (50, 35))
                            img_label = ttk.Label(method_frame, image=display_img)
                            img_label.image = display_img
                            img_label.pack(pady=2)

                            # Method label
                            method_label = ttk.Label(
                                method_frame, text=f"Method: {method_name}", font=("Arial", 8, "bold")
                            )
                            method_label.pack()

                            # Result info
                            UIHelpers.create_result_display(method_frame, text, confidence, rule_passed, rule_message)

                            # Add separator between methods (except last)
                            if i < len(engine_data) - 1:
                                sep = ttk.Separator(engine_row, orient="vertical")
                                sep.pack(side=tk.LEFT, fill=tk.Y, padx=2)

        except Exception as e:
            processing_error = True
            # Show error in results
            error_frame = ttk.LabelFrame(parent_frame, text=f"ROI: {roi_name} (ERROR)")
            error_frame.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(error_frame, text=f"Processing failed: {e}", foreground="red").pack(padx=5, pady=5)

        return early_exit_triggered, processing_error

    def _update_engine_options(self) -> None:
        # Update available OCR engine options
        available_engines = self.engine_selector.get_available_engines()
        self.engine_options = ["Auto-Select"]

        if "paddle_gpu" in available_engines:
            self.engine_options.append("PaddleOCR (GPU)")
        if "paddle_cpu" in available_engines:
            self.engine_options.append("PaddleOCR (CPU)")
        if "tesseract" in available_engines:
            self.engine_options.append("Tesseract")

    def get_engine_options(self) -> list:
        # Get available engine options for UI
        return self.engine_options

    def map_engine_to_display(self, engine_code: str) -> str:
        # Map internal engine code to display name
        mapping = {
            "auto": "Auto-Select",
            "paddle_gpu": "PaddleOCR (GPU)",
            "paddle_cpu": "PaddleOCR (CPU)",
            "tesseract": "Tesseract",
        }
        return mapping.get(engine_code, "Auto-Select")

    def map_display_to_engine(self, display_name: str) -> str:
        # Map display name to internal engine code
        mapping = {
            "Auto-Select": "auto",
            "PaddleOCR (GPU)": "paddle_gpu",
            "PaddleOCR (CPU)": "paddle_cpu",
            "Tesseract": "tesseract",
        }
        return mapping.get(display_name, "auto")

    def handle_engine_change(self, event, selected_roi_callback: Callable[[], Optional[ROIMeta]]) -> None:
        # Handle OCR engine selection change
        selected_engine = self.map_display_to_engine(self.ocr_engine_var.get())

        # If we have a selected ROI, suggest optimal scale for the new engine
        roi = selected_roi_callback()
        frame = self.get_frozen_frame() or self.get_current_frame()

        if roi and frame:
            # Get ROI image to calculate optimal scale
            roi_image = ImageUtils.crop_roi(frame, roi, self.padding_var.get())
            if roi_image:
                from ocr.engine_selector import EngineType

                engine_type = {
                    "paddle_gpu": EngineType.PADDLE_GPU,
                    "paddle_cpu": EngineType.PADDLE_CPU,
                    "tesseract": EngineType.TESSERACT,
                }.get(selected_engine, EngineType.PADDLE_GPU)

                optimal_scale = self.engine_selector.get_optimal_scale(roi_image, engine_type)
                print(f"Engine {selected_engine}: Optimal scale for current ROI: {optimal_scale:.2f}x")
