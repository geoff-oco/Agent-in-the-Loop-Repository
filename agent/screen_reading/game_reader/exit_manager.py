# Exit handling and user input monitoring
import threading
import time

try:
    import msvcrt  # Windows only
except ImportError:
    msvcrt = None


class ExitManager:  # Manages exit requests and keyboard monitoring

    def __init__(self):
        self.exit_requested = False
        self.exit_thread = None

    def _monitor_exit_key(self):
        # Background thread to monitor for 'x' key press
        if msvcrt is None:
            return  # Not on Windows, skip key monitoring

        while not self.exit_requested:
            try:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode("utf-8").lower()
                    if key == "x":
                        print("\n[Exit requested - 'x' key detected]")
                        self.exit_requested = True
                        break
                time.sleep(0.1)  # Small delay to prevent high CPU usage
            except Exception:
                break  # Exit on any error

    def start_exit_monitoring(self):
        # Start the exit monitoring thread
        if msvcrt is not None:
            self.exit_requested = False
            self.exit_thread = threading.Thread(target=self._monitor_exit_key, daemon=True)
            self.exit_thread.start()

    def check_exit_requested(self) -> bool:
        # Check if exit has been requested
        if self.exit_requested:
            print("Exiting game reader...")
            return True
        return False

    def reset(self):
        # Reset exit state (useful for restarting)
        self.exit_requested = False
