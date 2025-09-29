# Screen capture and display management
import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import os
from typing import Optional, Callable, Tuple

from core import ROIMeta, ROIManager
from imaging import get_screen_capture
from .ui_components import UIConfig


class CaptureManager:  # Handles screen capture, display and frame management
    def __init__(self, canvas: tk.Canvas, fps_var: tk.IntVar, source_var: tk.StringVar,
                 roi_manager: ROIManager, status_callback: Callable[[str], None],
                 get_selected_roi: Callable[[], Optional[str]],
                 schedule_callback: Callable[[], None]):
        self.canvas = canvas
        self.fps_var = fps_var
        self.source_var = source_var
        self.roi_manager = roi_manager
        self.status_callback = status_callback
        self.get_selected_roi = get_selected_roi
        self._schedule_next_tick = schedule_callback

        # Screen capture instance
        self.screen_capture = get_screen_capture()

        # Capture state
        self.capture_running = False
        self.sel_monitor_idx = 1

        # Frame state
        self.frame: Optional[Image.Image] = None  # latest full-res frame
        self.frozen: Optional[Image.Image] = None  # frozen full-res frame
        self.tkimg: Optional[ImageTk.PhotoImage] = None
        self.bg_image_id: Optional[int] = None  # persistent canvas image item
        self.is_drawing = False  # reentrancy guard

        # View scaling (canvas <-> image)
        self.view_scale: float = 1.0
        self.view_w: int = 0
        self.view_h: int = 0

    def refresh_monitors(self, combobox: tk.Widget) -> None:
        # Refresh available monitors using screen capture module
        monitors = self.screen_capture.get_monitors(refresh_cache=True)
        opts = [monitor["description"] for monitor in monitors]

        if not opts:
            opts = ["Monitor 1 (1920x1080) - Default"]

        combobox["values"] = opts
        if self.source_var.get() not in opts:
            self.source_var.set(opts[0])

    def start_capture(self) -> None:
        # Start screen capture
        if self.capture_running:
            return
        if not self.screen_capture.available:
            messagebox.showwarning("Capture", "MSS not installed.")
            return

        # Parse monitor index from selection
        source_text = self.source_var.get()
        try:
            # Extract monitor number from "Monitor X (...)" format
            if "Monitor" in source_text:
                self.sel_monitor_idx = int(source_text.split()[1])
            else:
                self.sel_monitor_idx = 1
        except (IndexError, ValueError):
            self.sel_monitor_idx = 1

        self.capture_running = True
        self._capture_tick()

    def stop_capture(self) -> None:
        # Stop screen capture
        self.capture_running = False

    def freeze_frame(self) -> None:
        # Freeze current frame
        if self.frame:
            self.frozen = self.frame.copy()
            self.status_callback("Frame frozen")

    def unfreeze_frame(self) -> None:
        # Unfreeze frame
        self.frozen = None
        self.status_callback("Frame unfrozen")

    def save_frame_png(self) -> None:
        # Save current frame as PNG
        frame = self.frozen or self.frame
        if frame is None:
            messagebox.showwarning("Save Frame", "No frame available")
            return

        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            frame.save(path)
            self.status_callback(f"Frame saved: {os.path.basename(path)}")

    def get_current_frame(self) -> Optional[Image.Image]:
        # Get the current frame
        return self.frame

    def get_frozen_frame(self) -> Optional[Image.Image]:
        # Get the frozen frame
        return self.frozen

    def set_frames(self, image: Image.Image) -> None:
        # Set both current and frozen frames
        self.frame = image
        self.frozen = image.copy()

    def draw_frame(self, frame: Image.Image) -> None:
        # Public method to draw a frame (used by template manager)
        self._draw_frame(frame)

    def redraw_frame_if_available(self) -> None:
        # Redraw the current or frozen frame if available
        frame = self.frozen or self.frame
        if frame:
            self._draw_frame(frame)

    def _capture_tick(self) -> None:
        # Smooth capture loop
        if not self.capture_running:
            return

        # When frozen, keep display steady (still allow capture to keep last frame fresh)
        if self.frozen is None:
            try:
                frame = self.screen_capture.capture_monitor(self.sel_monitor_idx)
                if frame:
                    self.frame = frame
                    self._draw_frame(frame)
            except Exception as e:
                self.status_callback(f"Capture error: {e}")

        # Schedule next tick through callback
        self._schedule_next_tick()

    def _draw_frame(self, frame: Image.Image) -> None:
        # Scale the frame to fit the canvas and draw ROIs over the scaled view
        if self.is_drawing:
            return
        self.is_drawing = True

        try:
            cw = self.canvas.winfo_width() or 1400
            ch = self.canvas.winfo_height() or 900
            scale = min(cw / frame.width, ch / frame.height)
            disp_w = max(1, int(frame.width * scale))
            disp_h = max(1, int(frame.height * scale))
            self.view_scale = scale
            self.view_w, self.view_h = disp_w, disp_h

            resized = frame.resize((disp_w, disp_h), Image.BICUBIC)
            self.tkimg = ImageTk.PhotoImage(resized)

            # Clear canvas and draw background
            self.canvas.delete("all")
            x_offset = (cw - disp_w) // 2
            y_offset = (ch - disp_h) // 2
            self.bg_image_id = self.canvas.create_image(x_offset, y_offset, image=self.tkimg, anchor=tk.NW)

            # Draw all ROIs
            self._draw_all_rois()

        finally:
            self.is_drawing = False

    def _draw_all_rois(self) -> None:
        # Draw all ROIs on canvas
        selected_name = self.get_selected_roi()
        for name, meta in self.roi_manager.rois.items():
            if self._roi_in_view(meta):
                self._draw_roi_with_handles(meta, selected=(name == selected_name))

    def _roi_in_view(self, meta: ROIMeta) -> bool:
        # Check if ROI is visible in current view
        return True  # For now, always draw all ROIs

    def roi_view_bbox(self, meta: ROIMeta) -> Tuple[int, int, int, int]:
        # Get ROI bounding box in view coordinates (public for use by studio)
        if not self.frame:
            return 0, 0, 0, 0

        # Calculate view offset (centering)
        cw = self.canvas.winfo_width() or 1400
        ch = self.canvas.winfo_height() or 900
        x_offset = (cw - self.view_w) // 2
        y_offset = (ch - self.view_h) // 2

        # Convert relative coordinates to view coordinates
        x = int(meta.x * self.view_w) + x_offset
        y = int(meta.y * self.view_h) + y_offset
        w = int(meta.w * self.view_w)
        h = int(meta.h * self.view_h)

        return x, y, w, h

    def _draw_roi_with_handles(self, meta: ROIMeta, selected: bool = False) -> None:
        # Draw ROI rectangle with proper colour coding and invisible handles
        x, y, w, h = self.roi_view_bbox(meta)

        if selected:
            # Selected ROI: full opacity, bright colour, with label
            outline = UIConfig.SELECTION_OUTLINE
            width = 3
            label_colour = outline
        else:
            # Unselected ROI: low opacity with muted label
            # Create a muted version of the default colour for low opacity effect
            colour = UIConfig.DEFAULT_ROI_COLOR
            r = int(colour[1:3], 16)
            g = int(colour[3:5], 16)
            b = int(colour[5:7], 16)

            # Blend with canvas background for low opacity effect
            bg_r, bg_g, bg_b = 34, 34, 34  # Dark background #222
            blend_factor = 0.3
            r = int(r * blend_factor + bg_r * (1 - blend_factor))
            g = int(g * blend_factor + bg_g * (1 - blend_factor))
            b = int(b * blend_factor + bg_b * (1 - blend_factor))

            outline = f"#{r:02x}{g:02x}{b:02x}"
            width = 1
            label_colour = outline

        # Draw ROI rectangle
        self.canvas.create_rectangle(x, y, x + w, y + h, outline=outline, width=width, fill="", tags="roi")

        # Draw ROI label
        label_x = x + 2
        label_y = y - 15 if y > 15 else y + h + 2
        self.canvas.create_text(
            label_x, label_y,
            text=meta.name,
            anchor=tk.NW,
            fill=label_colour,
            font=UIConfig.FONT_SMALL,
            tags="roi"
        )

        if selected:
            # Draw resize handles for selected ROI
            handle_size = UIConfig.HANDLE_SIZE
            handles = [
                (x - handle_size//2, y - handle_size//2, "nw"),  # top-left
                (x + w - handle_size//2, y - handle_size//2, "ne"),  # top-right
                (x - handle_size//2, y + h - handle_size//2, "sw"),  # bottom-left
                (x + w - handle_size//2, y + h - handle_size//2, "se"),  # bottom-right
            ]

            for hx, hy, handle_type in handles:
                self.canvas.create_rectangle(
                    hx, hy, hx + handle_size, hy + handle_size,
                    fill=UIConfig.HANDLE_FILL, outline=UIConfig.HANDLE_FILL,
                    tags=f"handle_{handle_type}"
                )


    def redraw_frame_if_available(self) -> None:
        # Redraw current frame if available (used for ROI updates)
        frame = self.frozen or self.frame
        if frame:
            self._draw_frame(frame)