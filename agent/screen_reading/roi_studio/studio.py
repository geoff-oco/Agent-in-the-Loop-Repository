# Live ROI Studio UI with modular architecture
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Optional, Tuple, List
from PIL import Image, ImageTk
import os

# Import all modular components
from core import ROIMeta, ROIManager, get_text_validator
from imaging import get_screen_capture, ImageUtils
from ocr import get_ocr_processor
from ocr.engine_selector import get_engine_selector

# Import shared UI components
from .ui_components import UIConfig, UIHelpers
from .mask_editor import MaskEditor
from .template_manager import TemplateManager
from .capture_manager import CaptureManager
from .ocr_tester import OCRTester


class LiveROIStudio:  # Live ROI Studio UI using dependency injection for all backend components.

    def __init__(self):
        # Inject dependencies
        self.roi_manager = ROIManager()
        self.ocr_processor = get_ocr_processor()
        self.text_validator = get_text_validator()
        self.engine_selector = get_engine_selector()
        self.current_roi_file = None  # Track current ROI file for auto-save

        # Mouse interaction state
        self.drag_state = None  # 'move' or 'resize_xx' where xx is handle position
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_roi_name = None
        self.original_roi_coords = None  # Store original ROI coords during drag

        # UI root
        self.root = tk.Tk()
        self.root.title("Live ROI Studio — Monitor Capture")
        self.root.geometry(UIConfig.DEFAULT_WINDOW_SIZE)

        # UI variables
        self.fps = tk.IntVar(value=UIConfig.DEFAULT_FPS)
        self.source_var = tk.StringVar(value=UIConfig.DEFAULT_MONITOR)

        # ROI selection state
        self.selected_name: Optional[str] = None

        # Character management
        self.accepted_chars = tk.StringVar(value=UIConfig.DEFAULT_ACCEPTED_CHARS)

        # Initialize mask editor after root is created
        self.mask_editor = MaskEditor(self.root)

        # Initialize template manager with placeholder callbacks (will be updated after capture manager)
        self.template_manager = TemplateManager(
            self.root,
            self.roi_manager,
            get_current_frame=lambda: None,  # Placeholder
            get_frozen_frame=lambda: None,   # Placeholder
            set_frames=lambda img: None,     # Placeholder
            draw_frame_callback=lambda img: None,  # Placeholder
            status_callback=self.status_message,
            get_selected_roi=lambda: self.selected_name,
            get_padding=lambda: self.var_padding.get(),
            stop_capture_callback=lambda: None  # Placeholder
        )

        # UI
        self._build_ui()
        self._build_right_panel()

        # Initialize capture manager after canvas is created
        self.capture_manager = CaptureManager(
            self.canvas,
            self.fps,
            self.source_var,
            self.roi_manager,
            self.status_message,
            lambda: self.selected_name,
            self._schedule_capture_tick
        )

        # Update template manager callbacks to use capture manager
        self.template_manager.get_current_frame = self.capture_manager.get_current_frame
        self.template_manager.get_frozen_frame = self.capture_manager.get_frozen_frame
        self.template_manager.set_frames = self.capture_manager.set_frames
        self.template_manager.draw_frame_callback = self.capture_manager.draw_frame
        self.template_manager.stop_capture_callback = self.capture_manager.stop_capture

        # Initialize OCR tester after all UI elements are created
        self.ocr_tester = OCRTester(
            self.roi_manager,
            self.capture_manager.get_current_frame,
            self.capture_manager.get_frozen_frame,
            lambda: self.selected_name,
            self.status_message,
            self.accepted_chars,
            self.var_padding,
            self.var_early_exit,
            self.var_preferred_method,
            self.var_ocr_engine,
            self.ent_expected,
            self.ent_pattern,
            self.ent_char_filter,
            self.var_filter_mode
        )

        # Now create the OCR tester preview section
        self.ocr_tester.create_preview_section(self.preview_tab_roi)

        # Update OCR engine options
        self.cmb_ocr_engine["values"] = self.ocr_tester.get_engine_options()

        self.capture_manager.refresh_monitors(self.cmb_source)
        self._update_file_status()  # Initialize file status display

    def run(self) -> None:
        # Start the main application loop
        self.root.mainloop()

    def _schedule_capture_tick(self) -> None:
        # Schedule the next capture tick
        if self.capture_manager.capture_running:
            delay = int(1000 / max(2, self.fps.get()))
            self.root.after(delay, self.capture_manager._capture_tick)

    # -------- UI Layout --------
    def _build_ui(self):
        tb = ttk.Frame(self.root)
        tb.pack(fill=tk.X, padx=UIConfig.TOOLBAR_PADX, pady=UIConfig.TOOLBAR_PADY)

        ttk.Button(tb, text="Start Capture", command=lambda: self.capture_manager.start_capture() if hasattr(self, 'capture_manager') else None).pack(side=tk.LEFT, padx=UIConfig.BUTTON_PADX)
        ttk.Button(tb, text="Stop Capture", command=lambda: self.capture_manager.stop_capture() if hasattr(self, 'capture_manager') else None).pack(side=tk.LEFT, padx=UIConfig.BUTTON_PADX)
        ttk.Button(tb, text="Freeze Frame", command=lambda: self.capture_manager.freeze_frame() if hasattr(self, 'capture_manager') else None).pack(
            side=tk.LEFT, padx=UIConfig.BUTTON_PADX_LARGE
        )
        ttk.Button(tb, text="Unfreeze", command=lambda: self.capture_manager.unfreeze_frame() if hasattr(self, 'capture_manager') else None).pack(side=tk.LEFT, padx=UIConfig.BUTTON_PADX)
        ttk.Button(tb, text="Save PNG Frame", command=lambda: self.capture_manager.save_frame_png() if hasattr(self, 'capture_manager') else None).pack(side=tk.LEFT, padx=UIConfig.BUTTON_PADX)

        ttk.Label(tb, text="Source:").pack(side=tk.LEFT, padx=(20, 4))
        self.cmb_source = ttk.Combobox(
            tb, textvariable=self.source_var, width=UIConfig.COMBOBOX_WIDTH, state="readonly"
        )
        self.cmb_source.pack(side=tk.LEFT)
        ttk.Button(tb, text="Refresh", command=lambda: self.capture_manager.refresh_monitors(self.cmb_source) if hasattr(self, 'capture_manager') else None).pack(side=tk.LEFT, padx=UIConfig.BUTTON_PADX)

        ttk.Label(tb, text="FPS").pack(side=tk.LEFT, padx=(20, 4))
        ttk.Spinbox(
            tb, from_=UIConfig.MIN_FPS, to=UIConfig.MAX_FPS, textvariable=self.fps, width=UIConfig.FPS_SPINBOX_WIDTH
        ).pack(side=tk.LEFT)

        ttk.Button(tb, text="Load ROIs", command=self.load_rois).pack(side=tk.RIGHT, padx=UIConfig.BUTTON_PADX)
        ttk.Button(tb, text="Export ROIs", command=self.save_rois).pack(side=tk.RIGHT, padx=UIConfig.BUTTON_PADX)

        main = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=UIConfig.MAIN_FRAME_PADX, pady=UIConfig.MAIN_FRAME_PADY)

        # Left: capture canvas
        self.canvas = tk.Canvas(main, bg=UIConfig.CANVAS_BG)
        main.add(self.canvas, weight=UIConfig.CANVAS_WEIGHT)

        # Right: controls
        self.right = ttk.Notebook(main)
        main.add(self.right, weight=UIConfig.RIGHT_PANEL_WEIGHT)

        self._bind_canvas_events()

    def _build_right_panel(self):
        # ROI Editor Tab
        self._build_roi_tab()

        # Template Tab
        self.template_manager.create_template_tab(self.right, self.mask_editor)

        # Character Settings Tab
        self._build_chars_tab()

    def _build_roi_tab(self):
        tab_roi = ttk.Frame(self.right)
        self.right.add(tab_roi, text="ROI Editor & Preview")

        # ROI Selection
        roi_sel_frame = ttk.LabelFrame(tab_roi, text="ROI Selection")
        roi_sel_frame.pack(fill=tk.X, padx=8, pady=8)

        sel_row = ttk.Frame(roi_sel_frame)
        sel_row.pack(fill=tk.X, padx=8, pady=8)

        self.cmb_roi_select = ttk.Combobox(sel_row, width=UIConfig.COMBOBOX_ROI_WIDTH, state="readonly")
        self.cmb_roi_select.pack(side=tk.LEFT, padx=4)
        self.cmb_roi_select.bind("<<ComboboxSelected>>", self.on_roi_dropdown_select)

        btn_frame = ttk.Frame(sel_row)
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(btn_frame, text="Delete", command=self.delete_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=2)

        # File Status
        file_status_frame = ttk.Frame(roi_sel_frame)
        file_status_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        ttk.Label(file_status_frame, text="Current File:").pack(side=tk.LEFT)
        self.lbl_current_file = ttk.Label(file_status_frame, text="None", foreground="gray")
        self.lbl_current_file.pack(side=tk.LEFT, padx=(5, 0))

        # ROI Details
        frm = ttk.LabelFrame(tab_roi, text="ROI Details")
        frm.pack(fill=tk.X, padx=8, pady=8)

        # Name and Coordinates (space-saving layout)
        name_coord_row = ttk.Frame(frm)
        name_coord_row.pack(fill=tk.X, padx=8, pady=4)

        ttk.Label(name_coord_row, text="Name:", width=6).pack(side=tk.LEFT)
        self.ent_name = ttk.Entry(name_coord_row, width=15)
        self.ent_name.pack(side=tk.LEFT, padx=4)

        ttk.Label(name_coord_row, text="X:", width=2).pack(side=tk.LEFT, padx=(8, 0))
        self.var_x = tk.DoubleVar()
        ttk.Entry(name_coord_row, textvariable=self.var_x, width=6).pack(side=tk.LEFT, padx=2)

        ttk.Label(name_coord_row, text="Y:", width=2).pack(side=tk.LEFT)
        self.var_y = tk.DoubleVar()
        ttk.Entry(name_coord_row, textvariable=self.var_y, width=6).pack(side=tk.LEFT, padx=2)

        ttk.Label(name_coord_row, text="W:", width=2).pack(side=tk.LEFT)
        self.var_w = tk.DoubleVar()
        ttk.Entry(name_coord_row, textvariable=self.var_w, width=6).pack(side=tk.LEFT, padx=2)

        ttk.Label(name_coord_row, text="H:", width=2).pack(side=tk.LEFT)
        self.var_h = tk.DoubleVar()
        ttk.Entry(name_coord_row, textvariable=self.var_h, width=6).pack(side=tk.LEFT, padx=2)

        # Notes
        notes_row = ttk.Frame(frm)
        notes_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(notes_row, text="Notes:", width=12).pack(side=tk.LEFT)
        self.ent_notes = ttk.Entry(notes_row, width=30)
        self.ent_notes.pack(side=tk.LEFT, padx=4)

        # Validation Settings
        val_frame = ttk.LabelFrame(tab_roi, text="Validation (Optional)")
        val_frame.pack(fill=tk.X, padx=8, pady=8)

        # Expected Values
        exp_row = ttk.Frame(val_frame)
        exp_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(exp_row, text="Expected:", width=12).pack(side=tk.LEFT)
        self.ent_expected = ttk.Entry(exp_row)
        self.ent_expected.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)

        # Pattern
        pat_row = ttk.Frame(val_frame)
        pat_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(pat_row, text="Pattern:", width=12).pack(side=tk.LEFT)
        self.ent_pattern = ttk.Entry(pat_row)
        self.ent_pattern.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)

        # OCR Settings
        ocr_frame = ttk.LabelFrame(tab_roi, text="OCR Settings")
        ocr_frame.pack(fill=tk.X, padx=8, pady=8)

        # Character Filter
        char_row = ttk.Frame(ocr_frame)
        char_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(char_row, text="Filter:", width=12).pack(side=tk.LEFT)
        self.ent_char_filter = ttk.Entry(char_row, width=15)
        self.ent_char_filter.pack(side=tk.LEFT, padx=4)

        self.var_filter_mode = tk.StringVar(value=UIConfig.DEFAULT_FILTER_MODE)
        ttk.Radiobutton(char_row, text="Whitelist", variable=self.var_filter_mode, value="whitelist").pack(
            side=tk.LEFT, padx=2
        )
        ttk.Radiobutton(char_row, text="Blacklist", variable=self.var_filter_mode, value="blacklist").pack(
            side=tk.LEFT, padx=2
        )

        # Padding
        pad_row = ttk.Frame(ocr_frame)
        pad_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(pad_row, text="Padding:", width=12).pack(side=tk.LEFT)
        self.var_padding = tk.IntVar(value=10)
        ttk.Entry(pad_row, textvariable=self.var_padding, width=8).pack(side=tk.LEFT, padx=4)

        # Preferred Method
        method_row = ttk.Frame(ocr_frame)
        method_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(method_row, text="Method:", width=12).pack(side=tk.LEFT)
        self.var_preferred_method = tk.StringVar(value=UIConfig.DEFAULT_OCR_METHOD)
        methods = [
            "Auto-Select",
            "Original",
            "Enhanced",
            "Binary",
            "Grey-Boost",
            "Inverted",
        ]
        ttk.Combobox(method_row, textvariable=self.var_preferred_method, values=methods, width=15).pack(
            side=tk.LEFT, padx=4
        )

        # OCR Engine Selection
        engine_row = ttk.Frame(ocr_frame)
        engine_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(engine_row, text="OCR Engine:", width=12).pack(side=tk.LEFT)
        self.var_ocr_engine = tk.StringVar(value=UIConfig.DEFAULT_OCR_ENGINE)

        self.cmb_ocr_engine = ttk.Combobox(
            engine_row, textvariable=self.var_ocr_engine, values=[], width=15, state="readonly"
        )
        self.cmb_ocr_engine.pack(side=tk.LEFT, padx=4)

        # Early exit optimization toggle
        self.var_early_exit = tk.BooleanVar(value=True)

        # Action buttons
        action_row = ttk.Frame(tab_roi)
        action_row.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(action_row, text="Save ROI", command=self.apply_to_selected_roi).pack(side=tk.LEFT, padx=4)
        self.lbl_save_status = ttk.Label(action_row, text="", foreground="green")
        self.lbl_save_status.pack(side=tk.LEFT, padx=8)

        # Live Preview & Testing (placeholder - will be created after OCR tester initialization)
        self.preview_tab_roi = tab_roi  # Store reference for later

    def _build_chars_tab(self):
        tab_chars = ttk.Frame(self.right)
        self.right.add(tab_chars, text="Character Settings")

        # Global character settings
        char_frame = ttk.LabelFrame(tab_chars, text="Default Character Set")
        char_frame.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(
            char_frame,
            text="Default character set that PaddleOCR can recognise (used when ROI has no specific filtering)",
            wraplength=300,
        ).pack(padx=8, pady=4)

        # Character entry
        char_entry_frame = ttk.Frame(char_frame)
        char_entry_frame.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(char_entry_frame, text="Characters:").pack(anchor=tk.W)
        char_text = tk.Text(char_entry_frame, height=6, wrap=tk.WORD)
        char_text.pack(fill=tk.X, pady=4)

        # Link text widget to StringVar
        def sync_chars(*args):
            char_text.delete("1.0", tk.END)
            char_text.insert("1.0", self.accepted_chars.get())

        def update_chars(*args):
            self.accepted_chars.set(char_text.get("1.0", tk.END).strip())

        self.accepted_chars.trace("w", sync_chars)
        char_text.bind("<KeyRelease>", update_chars)
        sync_chars()  # Initial sync

    def _bind_canvas_events(self):  # Bind canvas mouse events for ROI interaction
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Button-1>", self.on_down)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_up)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    def on_canvas_resize(self, e):  # Handle canvas resize events to auto-scale the image
        if hasattr(self, 'capture_manager'):
            self.capture_manager.redraw_frame_if_available()

    # -------- Essential ROI Management Methods --------
    def on_roi_dropdown_select(self, event):  # Handle ROI selection from dropdown
        name = self.cmb_roi_select.get()
        if name and name in self.roi_manager:
            self.selected_name = name
            roi = self.roi_manager[name]
            # Update form fields
            self.ent_name.delete(0, tk.END)
            self.ent_name.insert(0, roi.name)
            self.var_x.set(roi.x)
            self.var_y.set(roi.y)
            self.var_w.set(roi.w)
            self.var_h.set(roi.h)
            self.ent_notes.delete(0, tk.END)
            self.ent_notes.insert(0, roi.notes or "")
            self.ent_expected.delete(0, tk.END)
            self.ent_expected.insert(0, roi.expected_values or "")
            self.ent_pattern.delete(0, tk.END)
            self.ent_pattern.insert(0, roi.pattern or "")
            self.ent_char_filter.delete(0, tk.END)
            self.ent_char_filter.insert(0, roi.char_filter or "")
            if roi.filter_mode:
                self.var_filter_mode.set(roi.filter_mode)
            if roi.padding_pixels is not None:
                self.var_padding.set(roi.padding_pixels)
            if roi.preferred_method:
                self.var_preferred_method.set(roi.preferred_method)

            # Redraw to highlight selected ROI
            if hasattr(self, 'capture_manager'):
                self.capture_manager.redraw_frame_if_available()

    def apply_to_selected_roi(self):  # Apply current form settings to selected ROI
        if not self.selected_name or self.selected_name not in self.roi_manager:
            messagebox.showwarning("Apply ROI", "No ROI selected")
            return

        roi = self.roi_manager[self.selected_name]
        # Update ROI with form values
        roi.notes = self.ent_notes.get()
        roi.expected_values = self.ent_expected.get()
        roi.pattern = self.ent_pattern.get()
        roi.char_filter = self.ent_char_filter.get()
        roi.filter_mode = self.var_filter_mode.get()
        roi.padding_pixels = self.var_padding.get()
        roi.preferred_method = self.var_preferred_method.get()

        # Auto-save to file if we have one loaded
        if self.current_roi_file:
            try:
                success = self.roi_manager.save_to_file(self.current_roi_file)  # Returns boolean, not tuple
                if success:
                    self.lbl_save_status.config(text="✓ Saved to file", foreground="green")
                else:
                    self.lbl_save_status.config(text="✓ Saved (file write failed)", foreground="orange")
            except Exception as e:
                self.lbl_save_status.config(text=f"✓ Saved (file error: {str(e)[:20]})", foreground="orange")
        else:
            self.lbl_save_status.config(text="✓ Saved to memory", foreground="green")

        self.root.after(2000, lambda: self.lbl_save_status.config(text=""))

    def delete_selected(self):  # Delete selected ROI
        name = self.selected_name or self.cmb_roi_select.get()
        if not name:
            return

        if messagebox.askyesno("Delete", f"Delete ROI '{name}'?"):
            self.roi_manager.delete_roi(name)
            self.selected_name = None
            self._refresh_dropdowns()
            if hasattr(self, 'capture_manager'):
                self.capture_manager.redraw_frame_if_available()

    def clear_all(self):
        # Clear all ROIs from the canvas and manager
        if len(self.roi_manager) == 0:
            return

        if messagebox.askyesno("Clear", f"Delete all {len(self.roi_manager)} ROIs?"):
            count = self.roi_manager.clear_all()
            self.selected_name = None
            self.current_roi_file = None
            self._update_file_status()
            self.lbl_save_status.config(text="")
            self._refresh_dropdowns()
            if hasattr(self, 'capture_manager'):
                self.capture_manager.redraw_frame_if_available()

    def _refresh_dropdowns(self, select: Optional[str] = None):  # Refresh ROI dropdown with current ROIs
        names = self.roi_manager.get_roi_names()
        self.cmb_roi_select["values"] = names

        if select and select in names:
            self.cmb_roi_select.set(select)
            self.selected_name = select
        elif self.selected_name and self.selected_name in names:
            self.cmb_roi_select.set(self.selected_name)
        elif names:
            self.cmb_roi_select.set(names[0])
            self.selected_name = names[0] if names else None
        else:
            self.cmb_roi_select.set("")
            self.selected_name = None

    def _update_file_status(self):  # Update the current file status display
        if self.current_roi_file:
            filename = os.path.basename(self.current_roi_file)
            self.lbl_current_file.config(text=filename, foreground="black")
        else:
            self.lbl_current_file.config(text="None", foreground="gray")

    # -------- File Operations --------
    def save_rois(self):  # Save ROIs to file
        if len(self.roi_manager) == 0:
            messagebox.showwarning("Save ROIs", "No ROIs to save")
            return

        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            if self.roi_manager.save_to_file(path):
                self.current_roi_file = path
                self._update_file_status()
                self.status_message(f"Saved {len(self.roi_manager)} ROIs to {os.path.basename(path)}")
            else:
                messagebox.showerror("Save ROIs", "Failed to save ROIs")

    def load_rois(self):  # Load ROIs from file
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            success, message, count = self.roi_manager.load_from_file(path)
            if success:
                self.current_roi_file = path
                self._update_file_status()
                self._refresh_dropdowns()
                if hasattr(self, 'capture_manager'):
                    self.capture_manager.redraw_frame_if_available()
                self.status_message(f"Loaded {count} ROIs from {os.path.basename(path)}")
            else:
                messagebox.showerror("Load ROIs", f"Failed to load ROIs: {message}")

    # -------- Mouse Event Handlers --------
    def on_mouse_move(self, e):
        # Update cursor based on what's under the mouse
        if not hasattr(self, 'capture_manager') or not self.capture_manager.frame:
            return

        # Check if we're over a resize handle of selected ROI
        if self.selected_name and self.selected_name in self.roi_manager:
            handle = self._get_handle_at_position(e.x, e.y)
            if handle:
                # Set resize cursor based on handle position
                cursor_map = {
                    'nw': 'size_nw_se',
                    'ne': 'size_ne_sw',
                    'sw': 'size_ne_sw',
                    'se': 'size_nw_se',
                    'n': 'sb_v_double_arrow',
                    's': 'sb_v_double_arrow',
                    'e': 'sb_h_double_arrow',
                    'w': 'sb_h_double_arrow'
                }
                self.canvas.config(cursor=cursor_map.get(handle, 'arrow'))
                return

        # Check if we're over an ROI body
        roi_name = self._get_roi_at_position(e.x, e.y)
        if roi_name:
            self.canvas.config(cursor='fleur')  # Move cursor
        else:
            self.canvas.config(cursor='arrow')  # Default cursor

    def on_down(self, e):
        # Start drag operation
        if not hasattr(self, 'capture_manager') or not self.capture_manager.frame:
            return

        self.drag_start_x = e.x
        self.drag_start_y = e.y

        # Check for resize handle first (if ROI is selected)
        if self.selected_name and self.selected_name in self.roi_manager:
            handle = self._get_handle_at_position(e.x, e.y)
            if handle:
                self.drag_state = f'resize_{handle}'
                self.drag_roi_name = self.selected_name
                roi = self.roi_manager[self.selected_name]
                self.original_roi_coords = (roi.x, roi.y, roi.w, roi.h)
                return

        # Check for ROI body (for moving)
        roi_name = self._get_roi_at_position(e.x, e.y)
        if roi_name:
            # Select the ROI
            self.selected_name = roi_name
            self.cmb_roi_select.set(roi_name)
            self.on_roi_dropdown_select(None)  # Update form fields

            # Start move operation
            self.drag_state = 'move'
            self.drag_roi_name = roi_name
            roi = self.roi_manager[roi_name]
            self.original_roi_coords = (roi.x, roi.y, roi.w, roi.h)

            # Redraw to show selection
            if hasattr(self, 'capture_manager'):
                self.capture_manager.redraw_frame_if_available()

    def on_drag(self, e):
        # Handle dragging for move/resize
        if not self.drag_state or not self.drag_roi_name:
            return

        if not hasattr(self, 'capture_manager') or not self.capture_manager.frame:
            return

        roi = self.roi_manager[self.drag_roi_name]
        if not roi or not self.original_roi_coords:
            return

        # Calculate delta in screen coordinates
        dx = e.x - self.drag_start_x
        dy = e.y - self.drag_start_y

        # Convert delta to relative coordinates (0-1 range)
        view_w = self.capture_manager.view_w
        view_h = self.capture_manager.view_h
        if view_w <= 0 or view_h <= 0:
            return

        rel_dx = dx / view_w
        rel_dy = dy / view_h

        orig_x, orig_y, orig_w, orig_h = self.original_roi_coords

        if self.drag_state == 'move':
            # Move the ROI
            new_x = max(0, min(1 - orig_w, orig_x + rel_dx))
            new_y = max(0, min(1 - orig_h, orig_y + rel_dy))
            roi.x = new_x
            roi.y = new_y

        elif self.drag_state.startswith('resize_'):
            # Resize the ROI based on which handle is being dragged
            handle = self.drag_state[7:]  # Get handle position after 'resize_'

            if 'w' in handle:  # West (left) edge
                new_x = max(0, min(orig_x + orig_w - 0.01, orig_x + rel_dx))
                new_w = orig_w - (new_x - orig_x)
                roi.x = new_x
                roi.w = max(0.01, new_w)

            elif 'e' in handle:  # East (right) edge
                new_w = max(0.01, min(1 - orig_x, orig_w + rel_dx))
                roi.w = new_w

            if 'n' in handle:  # North (top) edge
                new_y = max(0, min(orig_y + orig_h - 0.01, orig_y + rel_dy))
                new_h = orig_h - (new_y - orig_y)
                roi.y = new_y
                roi.h = max(0.01, new_h)

            elif 's' in handle:  # South (bottom) edge
                new_h = max(0.01, min(1 - orig_y, orig_h + rel_dy))
                roi.h = new_h

        # Update form fields to reflect changes
        self.var_x.set(roi.x)
        self.var_y.set(roi.y)
        self.var_w.set(roi.w)
        self.var_h.set(roi.h)

        # Redraw the canvas
        if hasattr(self, 'capture_manager'):
            self.capture_manager.redraw_frame_if_available()

    def on_up(self, e):
        # End drag operation - no auto-save on drag
        self.drag_state = None
        self.drag_roi_name = None
        self.original_roi_coords = None
        self.canvas.config(cursor='arrow')

    def _get_roi_at_position(self, x, y):
        # Get the ROI at the given canvas position
        if not hasattr(self, 'capture_manager'):
            return None

        for name, roi in self.roi_manager.rois.items():
            roi_x, roi_y, roi_w, roi_h = self.capture_manager.roi_view_bbox(roi)
            if roi_x <= x <= roi_x + roi_w and roi_y <= y <= roi_y + roi_h:
                return name
        return None

    def _get_handle_at_position(self, x, y, threshold=5):  # Reduced threshold for smaller ROIs
        # Check if position is over a resize handle of selected ROI
        if not self.selected_name or self.selected_name not in self.roi_manager:
            return None

        if not hasattr(self, 'capture_manager'):
            return None

        roi = self.roi_manager[self.selected_name]
        roi_x, roi_y, roi_w, roi_h = self.capture_manager.roi_view_bbox(roi)

        # Check corners
        handles = [
            (roi_x, roi_y, 'nw'),
            (roi_x + roi_w, roi_y, 'ne'),
            (roi_x, roi_y + roi_h, 'sw'),
            (roi_x + roi_w, roi_y + roi_h, 'se'),
            (roi_x + roi_w // 2, roi_y, 'n'),
            (roi_x + roi_w // 2, roi_y + roi_h, 's'),
            (roi_x, roi_y + roi_h // 2, 'w'),
            (roi_x + roi_w, roi_y + roi_h // 2, 'e'),
        ]

        for hx, hy, handle_type in handles:
            if abs(x - hx) <= threshold and abs(y - hy) <= threshold:
                return handle_type

        return None

    # -------- Status and Utility --------
    def status_message(self, msg: str):
        # Display status message (could be expanded to status bar)
        print(f"Status: {msg}")


def main():
    # Main entry point for Live ROI Studio
    try:
        app = LiveROIStudio()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()