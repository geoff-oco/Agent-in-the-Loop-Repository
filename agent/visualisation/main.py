from external_overlay.external_overlay import ExternalOverlay
from ui import ui

# Global reference for overlay cleanup
overlay_instance = None

def main():
    global overlay_instance

    def ui_with_overlay_ref(tar_hwnd):
        return ui(tar_hwnd, overlay_instance)

    overlay_instance = ExternalOverlay("RTSViewer", ui_with_overlay_ref)
    overlay_instance.start()

if __name__ == "__main__":
    main()