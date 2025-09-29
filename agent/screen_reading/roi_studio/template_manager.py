# Template management and file operations
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image
import os
from typing import Optional, Callable

from core import ROIManager
from imaging import ImageUtils


class TemplateManager:  # Handles template creation, loading and saving functionality
    def __init__(self, parent_window: tk.Tk, roi_manager: ROIManager,
                 get_current_frame: Callable[[], Optional[Image.Image]],
                 get_frozen_frame: Callable[[], Optional[Image.Image]],
                 set_frames: Callable[[Image.Image], None],
                 draw_frame_callback: Callable[[Image.Image], None],
                 status_callback: Callable[[str], None],
                 get_selected_roi: Callable[[], Optional[str]],
                 get_padding: Callable[[], int],
                 stop_capture_callback: Callable[[], None]):
        self.parent_window = parent_window
        self.roi_manager = roi_manager
        self.get_current_frame = get_current_frame
        self.get_frozen_frame = get_frozen_frame
        self.set_frames = set_frames
        self.draw_frame_callback = draw_frame_callback
        self.status_callback = status_callback
        self.get_selected_roi = get_selected_roi
        self.get_padding = get_padding
        self.stop_capture_callback = stop_capture_callback

        # UI components (will be set by parent)
        self.template_info: Optional[ttk.Label] = None

    def create_template_tab(self, notebook: ttk.Notebook, mask_editor) -> None:
        # Create the template tab UI
        tab_template = ttk.Frame(notebook)
        notebook.add(tab_template, text="Template Creation")

        # Instructions
        instructions = ttk.LabelFrame(tab_template, text="Template System")
        instructions.pack(fill=tk.X, padx=8, pady=8)

        instruction_text = (
            "Create templates with enclosed ROI definitions for template-specific OCR calibration.\n\n"
            "1. Load template image or freeze current frame\n"
            "2. Define ROIs for this template\n"
            "3. Save template (PNG + JSON) for use with agents\n\n"
            "Output: Template PNG + ROI JSON compatible with realtime processing system"
        )

        ttk.Label(instructions, text=instruction_text, wraplength=300, justify=tk.LEFT).pack(padx=8, pady=8)

        # Template buttons
        btn_frame = ttk.Frame(tab_template)
        btn_frame.pack(fill=tk.X, padx=8, pady=8)

        ttk.Button(btn_frame, text="Load Template Image", command=self.load_template_image).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Save Template", command=self.save_roi_template).pack(fill=tk.X, pady=2)

        # Template info
        info_frame = ttk.LabelFrame(tab_template, text="Current Template")
        info_frame.pack(fill=tk.X, padx=8, pady=8)

        self.template_info = ttk.Label(info_frame, text="No template loaded")
        self.template_info.pack(padx=8, pady=8)

        # Mask Creation (Advanced)
        mask_frame = ttk.LabelFrame(tab_template, text="Mask Creation (Advanced)")
        mask_frame.pack(fill=tk.X, padx=8, pady=8)

        mask_help = ttk.Label(
            mask_frame,
            text="Create masks for loaded template images (white = match, black = ignore). Load template first!",
            wraplength=300,
            justify=tk.LEFT,
        )
        mask_help.pack(anchor="w", padx=4, pady=2)

        mask_btn_frame = ttk.Frame(mask_frame)
        mask_btn_frame.pack(fill=tk.X, padx=4, pady=4)

        ttk.Button(
            mask_btn_frame,
            text="Create Edge Mask",
            command=lambda: mask_editor.create_edge_mask(self.get_frozen_frame()),
        ).pack(fill=tk.X, pady=1)
        ttk.Button(
            mask_btn_frame,
            text="Create Custom Mask",
            command=lambda: mask_editor.create_custom_mask(self.get_frozen_frame()),
        ).pack(fill=tk.X, pady=1)

    def load_template_image(self) -> None:
        # Load template image from file
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif")])
        if not path:
            return

        try:
            image = Image.open(path)
            self.set_frames(image)
            self.stop_capture_callback()

            self.draw_frame_callback(image)
            if self.template_info:
                self.template_info.config(text=f"Template: {os.path.basename(path)}\nSize: {image.width}x{image.height}")
            self.status_callback(f"Template loaded: {os.path.basename(path)}")

        except Exception as e:
            messagebox.showerror("Load Template", f"Failed to load image: {e}")

    def save_roi_template(self) -> None:
        # Save current frame as template PNG
        frame = self.get_frozen_frame() or self.get_current_frame()
        if not frame:
            messagebox.showwarning("Save Template", "No image available")
            return

        # Check if a ROI is selected
        selected_name = self.get_selected_roi()
        if not selected_name or selected_name not in self.roi_manager:
            messagebox.showwarning("Save Template", "Please select a ROI first")
            return

        # Get the selected ROI and crop the frame to it
        roi = self.roi_manager[selected_name]
        roi_frame = ImageUtils.crop_roi(frame, roi, self.get_padding())

        if not roi_frame:
            messagebox.showerror("Save Template", "Failed to crop ROI from frame")
            return

        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            roi_frame.save(path)
            self.status_callback(f"ROI template saved: {os.path.basename(path)}")

