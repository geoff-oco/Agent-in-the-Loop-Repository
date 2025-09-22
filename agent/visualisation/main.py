from external_overlay.external_overlay import ExternalOverlay
from ui_new import ui

def main():
    overlay = ExternalOverlay("RTSViewer", ui)
    overlay.start()

if __name__ == "__main__":
    main()