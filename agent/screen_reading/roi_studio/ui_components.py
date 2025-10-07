# Shared UI components and configuration constants
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from typing import Optional


class UIConfig:  # Configuration constants for UI layout and styling
    # Visual styling
    DEFAULT_ROI_COLOR = "#00d1b2"
    HANDLE_SIZE = 6
    HANDLE_FILL = "#fbbf24"
    SELECTION_OUTLINE = "#fbbf24"
    CANVAS_BG = "#222"

    # Window dimensions
    DEFAULT_WINDOW_SIZE = "1920x1200"

    # Frame capture settings
    DEFAULT_FPS = 12
    MIN_FPS = 2
    MAX_FPS = 90
    FPS_SPINBOX_WIDTH = 5

    # UI spacing and padding
    TOOLBAR_PADX = 8
    TOOLBAR_PADY = 6
    BUTTON_PADX = 4
    BUTTON_PADX_LARGE = 12
    BUTTON_PADX_SECTION = 20
    MAIN_FRAME_PADX = 8
    MAIN_FRAME_PADY = 8

    # Widget dimensions
    COMBOBOX_WIDTH = 20
    COMBOBOX_ROI_WIDTH = 25

    # Canvas weights
    CANVAS_WEIGHT = 3
    RIGHT_PANEL_WEIGHT = 1

    # Default values
    DEFAULT_MONITOR = "Monitor 1"
    DEFAULT_ACCEPTED_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-:. "
    DEFAULT_FILTER_MODE = "whitelist"
    DEFAULT_OCR_METHOD = "Auto-Select"
    DEFAULT_OCR_ENGINE = "auto"

    # Font configurations
    FONT_DEFAULT = ("TkDefaultFont", 7)
    FONT_BOLD_SMALL = ("Arial", 8, "bold")
    FONT_BOLD_MEDIUM = ("Arial", 9, "bold")
    FONT_SMALL = ("Arial", 8)
    FONT_MEDIUM = ("Arial", 9)

    # Common colours
    COLOR_SUCCESS = "#006600"
    COLOR_ERROR = "#cc0000"
    COLOR_BLACK = "black"
    COLOR_GREEN = "green"
    COLOR_RED = "red"


class UIHelpers:  # Reusable UI component creation helpers
    @staticmethod
    def create_bold_label(parent: tk.Widget, text: str, size: str = "medium") -> ttk.Label:
        # Create a bold label with standard styling
        font = UIConfig.FONT_BOLD_MEDIUM if size == "medium" else UIConfig.FONT_BOLD_SMALL
        label = ttk.Label(parent, text=text, font=font)
        return label

    @staticmethod
    def create_info_label(parent: tk.Widget, text: str, colour: Optional[str] = None) -> ttk.Label:
        # Create an informational label with standard styling
        label = ttk.Label(parent, text=text, font=UIConfig.FONT_SMALL)
        if colour:
            label.configure(foreground=colour)
        return label

    @staticmethod
    def create_result_display(
        parent: tk.Widget, text: str, confidence: float, rule_passed: bool, rule_message: str = ""
    ) -> None:
        # Create a standardised result display with text, confidence and validation
        # Text result
        UIHelpers.create_bold_label(parent, "Text:", "small").pack(anchor=tk.W)
        text_label = ttk.Label(parent, text=text, wraplength=180)
        text_label.pack(anchor=tk.W, pady=2)

        # Confidence
        conf_colour = UIConfig.COLOR_GREEN if (confidence > 92.0 and rule_passed) else UIConfig.COLOR_BLACK
        conf_text = f"Confidence: {confidence:.1f}%"
        conf_label = UIHelpers.create_info_label(parent, conf_text, conf_colour)
        conf_label.pack(anchor=tk.W)

        # Rule result with message
        rule_colour = UIConfig.COLOR_SUCCESS if rule_passed else UIConfig.COLOR_ERROR
        rule_symbol = "✓" if rule_passed else "✗"

        if rule_message:
            rule_text = f"{rule_symbol} {rule_message}"
        else:
            rule_text = rule_symbol

        rule_label = UIHelpers.create_info_label(parent, rule_text, rule_colour)
        rule_label.pack(anchor=tk.W, pady=2)

    @staticmethod
    def create_button_row(parent: tk.Widget, buttons: list) -> ttk.Frame:
        # Create a horizontal row of buttons with standard spacing
        button_frame = ttk.Frame(parent)
        for button_config in buttons:
            text, command = button_config["text"], button_config["command"]
            padx = button_config.get("padx", UIConfig.BUTTON_PADX)
            ttk.Button(button_frame, text=text, command=command).pack(side=tk.LEFT, padx=padx)
        return button_frame

    @staticmethod
    def create_thumbnail_image(image: Image.Image, size: tuple = (80, 60)) -> ImageTk.PhotoImage:
        # Create a thumbnail image for display
        display_img = image.copy()
        display_img.thumbnail(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(display_img)
