"""
ROI Calibration tool for precise coordinate mapping.
Helps create accurate ROI definitions based on actual captures.
"""

import json
import os
import logging
from typing import Dict, Tuple, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from capture import ScreenCapture

logger = logging.getLogger(__name__)


class ROICalibrator:
    """Interactive GUI tool for defining screen regions for OCR processing."""

    def __init__(self):
        """Set up the calibrator window and initialize state variables."""
        # Main tkinter window
        self.root = tk.Tk()
        self.root.title("ROI Calibrator")
        self.root.geometry("1600x1000")
        self.root.state("zoomed")  # Maximize for better visibility

        # Image display components
        self.image = None  # Current image data
        self.image_path = None  # Path to loaded image
        self.canvas = None  # Display canvas
        self.photo = None  # Tkinter image format
        self.scale_factor = 1.0  # Display scaling

        # ROI tracking
        self.rois = {}  # Stored region definitions
        self.current_roi = None  # Currently selected ROI name

        # Mouse interaction state
        self.selection_start = None  # Mouse down position
        self.selection_rect = None  # Current selection rectangle

        # Special mode for action card templates
        self.template_mode = False

        self.setup_ui()

    def setup_ui(self):
        """Create the main UI components: controls, canvas, and ROI list."""
        self._create_control_panel()
        self._create_main_canvas()
        self._create_roi_panel()

    def _create_control_panel(self):
        """Create the top control bar with buttons and ROI selector."""
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # Image loading buttons
        ttk.Button(control_frame, text="Capture Game", command=self.capture_game).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Load Image", command=self.load_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Load Template", command=self.load_template).pack(side=tk.LEFT, padx=5)

        # ROI selection dropdown
        ttk.Label(control_frame, text="ROI:").pack(side=tk.LEFT, padx=5)
        self.roi_var = tk.StringVar()
        self.roi_dropdown = ttk.Combobox(control_frame, textvariable=self.roi_var)
        self.roi_dropdown["values"] = self._get_roi_options()
        self.roi_dropdown.pack(side=tk.LEFT, padx=5)
        self.roi_dropdown.bind("<<ComboboxSelected>>", self.on_roi_selected)

        # Coordinates display
        self.coords_label = ttk.Label(control_frame, text="Click and drag to select ROI")
        self.coords_label.pack(side=tk.LEFT, padx=20)

        # Action buttons (right side)
        ttk.Button(control_frame, text="Save ROIs", command=self.save_rois).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Load ROIs", command=self.load_rois).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Clear ROI", command=self.clear_current_roi).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Clear All", command=self.clear_all_rois).pack(side=tk.RIGHT, padx=5)

    def _create_main_canvas(self):
        """Create the scrollable canvas for image display and ROI selection."""
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Main canvas with scrollbars
        self.canvas = tk.Canvas(canvas_frame, bg="gray")
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)

        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Layout scrollbars and canvas
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mouse interaction events for ROI selection
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

    def _create_roi_panel(self):
        """Create the ROI list panel and status bar."""
        # Status bar at bottom
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # ROI list panel
        roi_list_frame = ttk.LabelFrame(self.root, text="Defined ROIs")
        roi_list_frame.pack(fill=tk.X, padx=10, pady=5)

        self.roi_listbox = tk.Listbox(roi_list_frame, height=6)
        self.roi_listbox.pack(fill=tk.X, padx=5, pady=5)
        self.roi_listbox.bind("<Double-Button-1>", self.on_roi_double_click)
        self.roi_listbox.bind("<Delete>", self.on_roi_delete_key)

        # Keyboard shortcuts for quick actions
        self.root.bind("<Control-s>", lambda e: self.save_rois())
        self.root.bind("<Control-o>", lambda e: self.load_rois())
        self.root.bind("<Delete>", lambda e: self.clear_current_roi())
        self.root.bind("<Control-Delete>", lambda e: self.clear_all_rois())

    def _get_roi_options(self):
        """Return list of available ROI names for the dropdown."""
        return [
            # System panels
            "phase_header",
            "ler_panel",
            "action_panel",
            # Blue base regions
            "blue_blue_units",
            "blue_blue_light_adj",
            "blue_blue_heavy_adj",
            "blue_blue_ranged_adj",
            "blue_red_units",
            # Red1 base regions
            "red1_blue_units",
            "red1_blue_light_adj",
            "red1_blue_heavy_adj",
            "red1_blue_ranged_adj",
            "red1_red_units",
            # Red2 base regions
            "red2_blue_units",
            "red2_blue_light_adj",
            "red2_blue_heavy_adj",
            "red2_blue_ranged_adj",
            "red2_red_units",
            # Red3 base regions
            "red3_blue_units",
            "red3_blue_light_adj",
            "red3_blue_heavy_adj",
            "red3_blue_ranged_adj",
            "red3_red_units",
            # Action card template regions
            "card_from_base",
            "card_to_base",
            "card_light_num",
            "card_heavy_num",
            "card_ranged_num",
            "card_lock",
        ]

    def _show_game_roi_help(self):
        """Show helpful information about game ROI calibration."""
        messagebox.showinfo(
            "Game ROI Calibration",
            "Game screenshot loaded! You can now define game ROIs:\n\n"
            "System Panels:\n"
            "- phase_header: Current phase number (top right)\n"
            "- ler_panel: Loss Exchange Ratio display\n"
            "- action_panel: Full action cards area\n\n"
            "Base Regions (for each faction):\n"
            "- [faction]_blue_units: Blue unit column (L/H/R numbers)\n"
            "- [faction]_red_units: Red unit column (L/H/R numbers)\n"
            "- [faction]_blue_[type]_adj: Individual adjustment cells\n\n"
            "Tips:\n"
            "- Use precise selection for better OCR accuracy\n"
            "- Coordinates are saved as relative values (0.0-1.0)\n"
            "- Double-click ROI list to edit existing regions\n"
            "- Use Ctrl+S to save, Ctrl+O to load ROI definitions",
        )

    def resize_window_for_template(self):
        """Switch to template mode with 1:1 pixel mapping for action card ROI calibration with changed scale."""
        if self.image is not None:
            template_h, template_w = self.image.shape[:2]

            # Account for UI space (controls, scrollbars, status bar)
            ui_padding_w = 80
            ui_padding_h = 180

            window_w = template_w + ui_padding_w
            window_h = template_h + ui_padding_h

            # Resize window for exact template fit
            self.root.geometry(f"{window_w}x{window_h}")
            self.root.minsize(window_w, window_h)
            self.canvas.configure(width=template_w, height=template_h)

            # Enable template mode for direct pixel mapping
            self.template_mode = True
            logger.info(f"Template mode: {template_w}x{template_h} → window {window_w}x{window_h}")

    def reset_to_normal_mode(self):
        """Reset to normal calibration mode for game screenshots."""
        self.template_mode = False

        # Reset window to default size
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        self.canvas.configure(width=0, height=0)  # Auto-expand with window
        logger.info("Reset to normal calibration mode")

    def capture_game(self):
        """Capture current game window or fallback to full screen."""
        self.reset_to_normal_mode()
        try:
            screen_capture = ScreenCapture()
            window_bounds, self.image = screen_capture.capture_target()

            if window_bounds:
                self.status_bar.config(text=f"Captured game window: {self.image.shape[1]}x{self.image.shape[0]}")
            else:
                self.status_bar.config(text=f"Captured screen: {self.image.shape[1]}x{self.image.shape[0]}")

            self.display_image()
            self._show_game_roi_help()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to capture game: {e}")
            logger.error(f"Capture failed: {e}")

    def load_image(self):
        """Load an image file from disk for ROI calibration."""
        self.reset_to_normal_mode()
        file_path = filedialog.askopenfilename(
            title="Select Screenshot",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff")],
        )

        if file_path:
            try:
                self.image = cv2.imread(file_path)
                self.image_path = file_path
                self.display_image()
                self.status_bar.config(text=f"Loaded: {os.path.basename(file_path)}")
                self._show_game_roi_help()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {e}")

    def load_template(self):
        """Load an action card template for ROI calibration."""
        # Set default to the screen_reading directory where templates are
        default_dir = os.path.dirname(__file__)

        file_path = filedialog.askopenfilename(
            title="Select Action Card Template",
            initialdir=default_dir,
            filetypes=[
                ("PNG files", "*.png"),
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff"),
            ],
        )

        if file_path:
            try:
                self.image = cv2.imread(file_path)
                self.image_path = file_path
                self.display_image()

                # For action card templates, resize window for 1:1 pixel mapping (no scaling)
                if "action_card" in os.path.basename(file_path).lower():
                    self.resize_window_for_template()
                    self.status_bar.config(text=f"Loaded template: {os.path.basename(file_path)} (1:1 pixel mapping)")
                else:
                    # Scale up other templates for easier ROI definition
                    if self.image.shape[0] < 400:  # If template is small
                        scale = 3.0
                        h, w = self.image.shape[:2]
                        self.image = cv2.resize(
                            self.image,
                            (int(w * scale), int(h * scale)),
                            interpolation=cv2.INTER_CUBIC,
                        )
                        self.status_bar.config(
                            text=f"Loaded template: {os.path.basename(file_path)} (scaled {scale}x for easier editing)"
                        )
                    else:
                        self.status_bar.config(text=f"Loaded template: {os.path.basename(file_path)}")

                # Show helpful message for template ROI definition
                messagebox.showinfo(
                    "Template Mode",
                    "Template loaded! You can now define card-specific ROIs:\n\n"
                    "- card_from_base: Left side base name (Blue/Red1/Red2/Red3)\n"
                    "- card_to_base: Right side base name\n"
                    "- card_light_num: Light unit number position\n"
                    "- card_heavy_num: Heavy unit number position\n"
                    "- card_ranged_num: Ranged unit number position\n"
                    "- card_lock: Lock icon position\n\n"
                    "These ROIs will be converted to relative coordinates for all card sizes.",
                )

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load template: {e}")

    def display_image(self):
        """Display the image on the canvas."""
        if self.image is None:
            return

        # Convert BGR to RGB for display
        display_image = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)

        # Calculate scale factor to fit canvas - allow scaling up for better visibility
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width > 1 and canvas_height > 1:  # Canvas is initialized
            img_height, img_width = display_image.shape[:2]

            scale_x = canvas_width / img_width
            scale_y = canvas_height / img_height
            # For action card templates, use 1:1 scaling for perfect coordinate mapping
            if self.template_mode:
                self.scale_factor = 1.0  # Perfect 1:1 pixel mapping for action cards
                print(f"Using 1:1 scaling for action card template (no scaling)")
            else:
                self.scale_factor = min(scale_x, scale_y, 2.0)  # Allow up to 2x scaling for better visibility

            new_width = int(img_width * self.scale_factor)
            new_height = int(img_height * self.scale_factor)

            display_image = cv2.resize(display_image, (new_width, new_height))

        # Convert to PIL Image and then to PhotoImage
        pil_image = Image.fromarray(display_image)
        self.photo = ImageTk.PhotoImage(pil_image)

        # Clear canvas and add image
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

        # Update scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        # Draw existing ROIs
        self.draw_existing_rois()

    def draw_existing_rois(self):
        """Draw all existing ROIs on the canvas."""
        if not self.image is None:
            img_height, img_width = self.image.shape[:2]

            for name, roi in self.rois.items():
                if isinstance(roi, (list, tuple)) and len(roi) == 4:
                    # Convert relative to absolute coordinates
                    x = int(roi[0] * img_width * self.scale_factor)
                    y = int(roi[1] * img_height * self.scale_factor)
                    w = int(roi[2] * img_width * self.scale_factor)
                    h = int(roi[3] * img_height * self.scale_factor)

                    # Draw rectangle
                    color = "red" if name == self.current_roi else "blue"
                    self.canvas.create_rectangle(x, y, x + w, y + h, outline=color, width=2, tags=f"roi_{name}")
                    self.canvas.create_text(
                        x,
                        y - 10,
                        anchor=tk.SW,
                        text=name,
                        fill=color,
                        tags=f"roi_{name}",
                    )

    def on_roi_selected(self, event):
        """Handle ROI selection from dropdown."""
        self.current_roi = self.roi_var.get()
        self.draw_existing_rois()  # Redraw to highlight current ROI

    def on_mouse_down(self, event):
        """Handle mouse down event."""
        if self.current_roi:
            self.selection_start = (
                self.canvas.canvasx(event.x),
                self.canvas.canvasy(event.y),
            )

    def on_mouse_drag(self, event):
        """Handle mouse drag event."""
        if self.selection_start and self.current_roi:
            current_pos = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

            # Remove previous selection rectangle
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)

            # Draw new selection rectangle
            self.selection_rect = self.canvas.create_rectangle(
                self.selection_start[0],
                self.selection_start[1],
                current_pos[0],
                current_pos[1],
                outline="green",
                width=2,
                dash=(5, 5),
            )

            # Update coordinates display
            x1, y1 = self.selection_start
            x2, y2 = current_pos

            # Convert to image coordinates
            img_x1 = int(min(x1, x2) / self.scale_factor)
            img_y1 = int(min(y1, y2) / self.scale_factor)
            img_w = int(abs(x2 - x1) / self.scale_factor)
            img_h = int(abs(y2 - y1) / self.scale_factor)

            self.coords_label.config(text=f"Selection: ({img_x1}, {img_y1}, {img_w}, {img_h})")

    def on_mouse_up(self, event):
        """Handle mouse up event."""
        if self.selection_start and self.current_roi and self.image is not None:
            current_pos = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

            # Calculate ROI in image coordinates
            x1, y1 = self.selection_start
            x2, y2 = current_pos

            img_x = min(x1, x2) / self.scale_factor
            img_y = min(y1, y2) / self.scale_factor
            img_w = abs(x2 - x1) / self.scale_factor
            img_h = abs(y2 - y1) / self.scale_factor

            # Convert to relative coordinates
            img_height, img_width = self.image.shape[:2]
            rel_x = img_x / img_width
            rel_y = img_y / img_height
            rel_w = img_w / img_width
            rel_h = img_h / img_height

            # Store ROI
            self.rois[self.current_roi] = [rel_x, rel_y, rel_w, rel_h]

            # Update ROI list
            self.update_roi_list()

            # Clean up selection
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)
                self.selection_rect = None
            self.selection_start = None

            # Redraw ROIs
            self.draw_existing_rois()

            self.status_bar.config(
                text=f"Defined ROI '{self.current_roi}': {rel_x:.3f}, {rel_y:.3f}, {rel_w:.3f}, {rel_h:.3f}"
            )

    def update_roi_list(self):
        """Update the ROI list display."""
        self.roi_listbox.delete(0, tk.END)
        for name, roi in self.rois.items():
            roi_str = f"{name}: ({roi[0]:.3f}, {roi[1]:.3f}, {roi[2]:.3f}, {roi[3]:.3f})"
            self.roi_listbox.insert(tk.END, roi_str)

    def on_roi_double_click(self, event):
        """Handle double-click on ROI list."""
        selection = self.roi_listbox.curselection()
        if selection:
            roi_text = self.roi_listbox.get(selection[0])
            roi_name = roi_text.split(":")[0]
            self.roi_var.set(roi_name)
            self.current_roi = roi_name
            self.draw_existing_rois()

    def on_roi_delete_key(self, event):
        """Handle delete key press on ROI list."""
        selection = self.roi_listbox.curselection()
        if selection:
            roi_text = self.roi_listbox.get(selection[0])
            roi_name = roi_text.split(":")[0]

            if roi_name in self.rois:
                result = messagebox.askyesno("Confirm", f"Delete ROI '{roi_name}'?")
                if result:
                    del self.rois[roi_name]
                    self.update_roi_list()
                    self.draw_existing_rois()
                    self.status_bar.config(text=f"Deleted ROI '{roi_name}'")

    def save_rois(self):
        """Save ROIs to JSON file."""
        if not self.rois:
            messagebox.showwarning("Warning", "No ROIs defined")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save ROIs",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
        )

        if file_path:
            try:
                with open(file_path, "w") as f:
                    json.dump(self.rois, f, indent=2)
                messagebox.showinfo("Success", f"ROIs saved to {file_path}")
                self.status_bar.config(text=f"Saved ROIs to {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save ROIs: {e}")

    def load_rois(self):
        """Load ROIs from JSON file."""
        file_path = filedialog.askopenfilename(title="Load ROIs", filetypes=[("JSON files", "*.json")])

        if file_path:
            try:
                with open(file_path, "r") as f:
                    self.rois = json.load(f)
                self.update_roi_list()
                self.draw_existing_rois()
                messagebox.showinfo("Success", f"Loaded {len(self.rois)} ROIs")
                self.status_bar.config(text=f"Loaded ROIs from {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load ROIs: {e}")

    def clear_current_roi(self):
        """Clear the currently selected ROI."""
        if not self.current_roi:
            messagebox.showwarning("Warning", "No ROI selected")
            return

        if self.current_roi in self.rois:
            # Confirm deletion
            result = messagebox.askyesno("Confirm", f"Delete ROI '{self.current_roi}'?")
            if result:
                del self.rois[self.current_roi]
                self.update_roi_list()
                self.draw_existing_rois()
                self.status_bar.config(text=f"Cleared ROI '{self.current_roi}'")
        else:
            messagebox.showinfo("Info", f"ROI '{self.current_roi}' is not defined")

    def clear_all_rois(self):
        """Clear all ROIs."""
        if not self.rois:
            messagebox.showinfo("Info", "No ROIs to clear")
            return

        result = messagebox.askyesno("Confirm", f"Delete all {len(self.rois)} ROIs?")
        if result:
            self.rois.clear()
            self.update_roi_list()
            self.draw_existing_rois()
            self.status_bar.config(text="Cleared all ROIs")

    def run(self):
        """Start the calibration tool."""
        self.root.mainloop()


def main():
    """Run the ROI calibrator."""
    try:
        calibrator = ROICalibrator()
        calibrator.run()
    except Exception as e:
        print(f"Calibrator failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
