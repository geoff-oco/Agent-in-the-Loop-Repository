# Custom mask creation and editing functionality
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import os
from typing import Tuple


class MaskEditor:  # Handles custom mask creation and edge detection functionality
    def __init__(self, parent_window: tk.Tk):
        self.parent_window = parent_window

    def create_edge_mask(self, frozen_image: Image.Image) -> None:
        # Create a mask using edge detection to focus on structural features
        if frozen_image is None:
            messagebox.showwarning("Mask Creation", "No template image loaded. Use 'Load Template Image' first.")
            return

        try:
            import cv2
            import numpy as np
        except ImportError:
            messagebox.showerror("Mask Creation", "OpenCV not available for mask creation")
            return

        try:
            # Use the full template image for mask creation
            crop = frozen_image
            gray = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150)

            # Dilate edges to create mask regions
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.dilate(edges, kernel, iterations=1)

            # Save mask
            path = filedialog.asksaveasfilename(
                defaultextension=".png", filetypes=[("PNG", "*.png")], title="Save Edge Mask"
            )
            if path:
                cv2.imwrite(path, mask)
                messagebox.showinfo("Mask Creation", f"Saved edge mask: {os.path.basename(path)}")

        except Exception as e:
            messagebox.showerror("Mask Creation", f"Failed to create mask: {e}")

    def create_custom_mask(self, frozen_image: Image.Image) -> None:
        # Create a custom mask using a simple paint tool
        if frozen_image is None:
            messagebox.showwarning("Mask Creation", "No template image loaded. Use 'Load Template Image' first.")
            return

        try:
            import cv2
            import numpy as np
        except ImportError:
            messagebox.showerror("Mask Creation", "OpenCV not available for custom mask creation")
            return

        # Use the full template image for mask creation
        crop = frozen_image

        # Setup mask editor components
        mask_window, mask_canvas = self._setup_mask_editor_window(crop)
        mask_data = self._initialise_mask_data(crop, mask_canvas)
        self._setup_mask_painting(mask_canvas, mask_data)
        self._setup_mask_controls(mask_window, mask_canvas, mask_data)

    def _setup_mask_editor_window(self, crop: Image.Image) -> Tuple[tk.Toplevel, tk.Canvas]:
        # Create and configure the mask editor window
        mask_window = tk.Toplevel(self.parent_window)
        mask_window.title("Custom Mask Editor")
        mask_window.geometry("600x500")

        help_text = (
            "Left click/drag: Paint WHITE (match areas)\n"
            "Right click/drag: Paint BLACK (ignore areas)\n"
            "Clear: Reset to all black (ignore all)"
        )
        ttk.Label(mask_window, text=help_text).pack(pady=5)

        # Canvas for mask editing
        canvas_frame = ttk.Frame(mask_window)
        canvas_frame.pack(expand=True, fill=tk.BOTH)

        mask_canvas = tk.Canvas(canvas_frame, width=crop.width * 2, height=crop.height * 2, bg="gray")
        mask_canvas.pack()

        return mask_window, mask_canvas

    def _initialise_mask_data(self, crop: Image.Image, mask_canvas: tk.Canvas):
        # Initialise mask data and canvas display
        import numpy as np

        if self._is_likely_mask(crop):
            # Use existing mask as starting point
            gray_crop = crop.convert("L")
            mask_data = np.array(gray_crop)
            photo_ref = ImageTk.PhotoImage(crop.resize((crop.width * 2, crop.height * 2), Image.NEAREST))
            mask_canvas.create_image(0, 0, anchor=tk.NW, image=photo_ref)

            # Draw existing mask areas on canvas
            for y in range(mask_data.shape[0]):
                for x in range(mask_data.shape[1]):
                    if mask_data[y, x] > 128:  # White areas
                        mask_canvas.create_rectangle(
                            x * 2,
                            y * 2,
                            (x + 1) * 2,
                            (y + 1) * 2,
                            fill="white",
                            outline="white",
                            width=0,
                            tags="mask_paint",
                        )
        else:
            # Start with blank mask for regular images
            mask_data = np.zeros((crop.height, crop.width), dtype=np.uint8)
            photo_ref = ImageTk.PhotoImage(crop.resize((crop.width * 2, crop.height * 2), Image.NEAREST))
            mask_canvas.create_image(0, 0, anchor=tk.NW, image=photo_ref)

        # Keep reference to prevent garbage collection
        mask_canvas.photo_ref = photo_ref
        return mask_data

    def _setup_mask_painting(self, mask_canvas: tk.Canvas, mask_data):
        # Setup mask painting functionality
        def paint_mask(event, colour=255):
            x, y = event.x // 2, event.y // 2  # Scale down to mask coordinates
            if 0 <= x < mask_data.shape[1] and 0 <= y < mask_data.shape[0]:
                # Paint 3x3 area for easier use
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < mask_data.shape[1] and 0 <= ny < mask_data.shape[0]:
                            mask_data[ny, nx] = colour
                            # Update canvas
                            mask_canvas.create_rectangle(
                                nx * 2,
                                ny * 2,
                                (nx + 1) * 2,
                                (ny + 1) * 2,
                                fill="white" if colour == 255 else "black",
                                outline="white" if colour == 255 else "black",
                                width=0,
                                tags="mask_paint",
                            )

        def paint_white(event):
            paint_mask(event, 255)

        def paint_black(event):
            paint_mask(event, 0)

        # Bind painting events
        mask_canvas.bind("<B1-Motion>", paint_white)
        mask_canvas.bind("<Button-1>", paint_white)
        mask_canvas.bind("<B3-Motion>", paint_black)
        mask_canvas.bind("<Button-3>", paint_black)

        return paint_white, paint_black

    def _setup_mask_controls(self, mask_window: tk.Toplevel, mask_canvas: tk.Canvas, mask_data):
        # Setup control buttons for the mask editor
        import cv2

        button_frame = ttk.Frame(mask_window)
        button_frame.pack(pady=10)

        def save_mask():
            path = filedialog.asksaveasfilename(
                defaultextension=".png", filetypes=[("PNG", "*.png")], title="Save Custom Mask"
            )
            if path:
                try:
                    cv2.imwrite(path, mask_data)
                except:
                    Image.fromarray(mask_data).save(path)
                messagebox.showinfo("Mask Creation", f"Saved custom mask: {os.path.basename(path)}")
                mask_window.destroy()

        def clear_mask():
            mask_data.fill(0)
            mask_canvas.delete("mask_paint")

        ttk.Button(button_frame, text="Clear", command=clear_mask).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Mask", command=save_mask).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=mask_window.destroy).pack(side=tk.LEFT, padx=5)

    def _is_likely_mask(self, img: Image.Image) -> bool:
        # Check if an image is likely a mask (mostly black and white)
        try:
            import numpy as np

            # Convert to grayscale and check histogram
            gray = img.convert("L")
            arr = np.array(gray)
            hist = np.histogram(arr, bins=256)[0]
            # Count pixels near black (0-50) and white (200-255)
            black_pixels = np.sum(hist[0:51])
            white_pixels = np.sum(hist[200:256])
            total_pixels = arr.size
            # If more than 80% of pixels are near black or white, it's likely a mask
            return (black_pixels + white_pixels) / total_pixels > 0.8
        except:
            return False
