import ctypes
import ctypes.wintypes
import subprocess
import psutil
import os

# Windows API constants
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_INFORMATION = 0x0400

# Windows API functions
kernel32 = ctypes.windll.kernel32
kernel32.TerminateProcess.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.UINT]
kernel32.TerminateProcess.restype = ctypes.wintypes.BOOL

kernel32.OpenProcess.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD]
kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE

kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
kernel32.CloseHandle.restype = ctypes.wintypes.BOOL


def terminate_process_tree_aggressive(pid):
    # Nuclear option - immediately terminate process tree using WinAPI
    try:
        # Use taskkill with /F /T flags for immediate force termination of tree
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=2)
        print(f"Terminated process tree for PID {pid} with taskkill")
        return True
    except Exception as e:
        print(f"Taskkill failed: {e}")

    # Fallback to direct WinAPI termination
    try:
        # Get all child processes recursively
        parent = psutil.Process(pid)
        all_procs = [parent] + parent.children(recursive=True)

        for proc in all_procs:
            try:
                # Open process with terminate permissions
                handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, proc.pid)
                if handle:
                    # Immediately terminate with exit code 1
                    kernel32.TerminateProcess(handle, 1)
                    kernel32.CloseHandle(handle)
                    print(f"Force terminated PID {proc.pid}")
            except:
                pass
        return True
    except Exception as e:
        print(f"WinAPI termination failed: {e}")
        return False


def kill_python_processes_by_script(script_name, exclude_current_pid=True):
    # Kill all Python processes running specific script
    killed_count = 0
    current_pid = os.getpid()

    # CRITICAL: Never kill main.py (UI process) to prevent UI crash during cancel
    ui_scripts = ["main.py", "ui.py"]

    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["name"] and "python" in proc.info["name"].lower():
                    if proc.info["cmdline"] and any(script_name in arg for arg in proc.info["cmdline"]):
                        # Skip current process if requested
                        if exclude_current_pid and proc.info["pid"] == current_pid:
                            print(f"Skipping current UI process: PID {proc.info['pid']}")
                            continue

                        # CRITICAL: Never kill UI processes (main.py, ui.py) regardless of script_name
                        if proc.info["cmdline"] and any(
                            ui_script in arg for ui_script in ui_scripts for arg in proc.info["cmdline"]
                        ):
                            print(f"SAFETY: Skipping UI process main.py/ui.py: PID {proc.info['pid']}")
                            continue

                        print(f"Found Python process running {script_name}: PID {proc.info['pid']}")
                        terminate_process_tree_aggressive(proc.info["pid"])
                        killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        print(f"Error scanning for Python processes: {e}")

    return killed_count


def selective_shutdown():
    # More selective shutdown - only kill LIVE_GAME_READER and related processes
    print("SELECTIVE SHUTDOWN - Terminating game reader processes...")

    # Kill any LIVE_GAME_READER processes
    killed = kill_python_processes_by_script("LIVE_GAME_READER.py", exclude_current_pid=True)
    print(f"Killed {killed} LIVE_GAME_READER processes")

    # Kill cmd windows with our batch file title only if needed
    try:
        subprocess.run(
            ["taskkill", "/F", "/FI", "WINDOWTITLE eq Agent-in-the-Loop System Launcher*"],
            capture_output=True,
            timeout=1,
        )
    except:
        pass


def nuclear_shutdown_delayed():
    # Nuclear option but delayed - for use after UI shutdown
    import threading

    def delayed_kill():
        import time

        time.sleep(1)  # Give UI time to shut down gracefully
        print("DELAYED NUCLEAR SHUTDOWN - Killing remaining processes...")

        # Now kill everything including UI processes
        kill_python_processes_by_script("main.py", exclude_current_pid=False)

        # Kill any remaining Python processes from our directory
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))

            for proc in psutil.process_iter(["pid", "name", "cwd"]):
                try:
                    if (
                        proc.info["name"]
                        and "python" in proc.info["name"].lower()
                        and proc.info["cwd"]
                        and project_root in proc.info["cwd"]
                    ):
                        terminate_process_tree_aggressive(proc.info["pid"])
                except:
                    pass
        except:
            pass

    # Start delayed shutdown in background
    thread = threading.Thread(target=delayed_kill, daemon=True)
    thread.start()
