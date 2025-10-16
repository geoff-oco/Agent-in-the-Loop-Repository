import dearpygui.dearpygui as dpg
import threading
from multiprocessing import Process
import subprocess
import time
import psutil
import win32gui
import win32process
import sys
import os
import json
import shutil
import stats
from typing import Optional
from win_termination import (
    terminate_process_tree_aggressive,
    selective_shutdown,
    nuclear_shutdown_delayed,
)
from agent_bridge import AgentBridge


# Clean up temporary files from previous sessions on startup
def _cleanup_temp_files():
    from pathlib import Path

    print("Cleaning up temporary files from previous sessions...")
    cleanup_count = 0

    try:
        # Get project root (2 levels up from this file: agent/visualisation/ui.py)
        project_root = Path(__file__).parent.parent.parent

        # Clean agent reply files (both game_state.txt and simple_game_state.txt)
        agent_replies_dir = project_root / "agent" / "decision_logic" / "run_agent" / "agent_replies"
        if agent_replies_dir.exists():
            for reply_file in agent_replies_dir.glob("*.txt"):
                try:
                    reply_file.unlink()
                    print(f"  Removed: {reply_file.name}")
                    cleanup_count += 1
                except Exception as e:
                    print(f"  Warning: Could not remove {reply_file.name}: {e}")

        # Clean game state files in agent directory (game_state.json, simple_game_state.json)
        game_state_dir = project_root / "agent" / "decision_logic" / "run_agent" / "game_state"
        if game_state_dir.exists():
            for state_file in game_state_dir.glob("*.json"):
                try:
                    state_file.unlink()
                    print(f"  Removed: {state_file.name}")
                    cleanup_count += 1
                except Exception as e:
                    print(f"  Warning: Could not remove {state_file.name}: {e}")

        # Clean finalOutput.txt (in visualisation directory)
        final_output = Path(__file__).parent / "finalOutput.txt"
        if final_output.exists():
            try:
                final_output.unlink()
                print(f"  Removed: finalOutput.txt")
                cleanup_count += 1
            except Exception as e:
                print(f"  Warning: Could not remove finalOutput.txt: {e}")

        # Limit output sessions to 10 most recent (delete oldest by timestamp)
        output_dir = project_root / "agent" / "screen_reading" / "output"
        if output_dir.exists():
            # Get all game_session_* directories
            session_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith("game_session_")]

            # Sort by directory name (timestamp in name: game_session_YYYYMMDD_HHMMSS)
            # Newest first (reverse=True)
            session_dirs.sort(key=lambda x: x.name, reverse=True)

            # Keep only the 10 most recent, delete the rest
            if len(session_dirs) > 10:
                sessions_to_delete = session_dirs[10:]  # Everything after index 10
                for session_dir in sessions_to_delete:
                    try:
                        shutil.rmtree(session_dir)
                        print(f"  Removed old session: {session_dir.name}")
                        cleanup_count += 1
                    except Exception as e:
                        print(f"  Warning: Could not remove {session_dir.name}: {e}")

        print(f"Cleanup complete: {cleanup_count} file(s) removed")

    except Exception as e:
        print(f"Error during cleanup: {e}")
        print("Continuing with startup...")


running = False  # Only global state flag we need - controls all operations
hidden = False
overlay_instance = None
current_process = None
current_subprocess = None
current_agent_subprocess = None

# Font and theme references for popup windows
font_arial_global = None
font_arialBold_global = None
global_theme_ref = None


def ui(tar_hwnd=None, overlay=None):
    # Clean up temporary files from previous sessions
    _cleanup_temp_files()

    # Store overlay reference for callbacks
    global overlay_instance, font_arial_global, font_arialBold_global, global_theme_ref
    overlay_instance = overlay

    # Dont start drawing screen while window is minimised
    while win32gui.IsIconic(tar_hwnd):
        pass

    time.sleep(0.1)
    start_size = win32gui.GetWindowRect(tar_hwnd)
    window_height = start_size[3] - start_size[1]
    window_width = start_size[2] - start_size[0]

    # Adds fonts
    FONT_SCALE = 2
    font_is_loaded = True
    with dpg.font_registry():
        try:
            font_arial = dpg.add_font("C:/Windows/Fonts/arial.ttf", 7 * FONT_SCALE)
            font_arialBold = dpg.add_font("C:/Windows/Fonts/arialbd.ttf", 7 * FONT_SCALE)
            # Store fonts globally for popup access
            font_arial_global = font_arial
            font_arialBold_global = font_arialBold
        except SystemError:
            print("Could not find font... switching to default")
            font_is_loaded = False

    # Main container window for buttons (resizable)
    with dpg.window(
        tag="buttons_container",
        no_background=False,
        no_move=False,
        no_resize=False,
        no_title_bar=True,
        width=220,
        height=280,
        pos=(40, (window_height / 3)),
    ):

        if font_is_loaded:
            dpg.bind_item_font(dpg.last_item(), font_arialBold)
        dpg.add_text("System Controls", color=(200, 200, 200))

        # Child window inside for actual button content (makes it resizable)
        with dpg.child_window(tag="buttons_win", width=-1, auto_resize_y=True):
            with dpg.group(tag="agent_button"):
                dpg.add_button(label="Generate Strategy", width=-1, callback=_generation_callback)
            with dpg.group(tag="cancel_button", enabled=False):
                dpg.add_button(label="Cancel", width=-1, callback=_stopButton_callback)
            dpg.add_spacer(height=5)
            dpg.add_separator()
            dpg.add_spacer(height=5)
            dpg.add_button(label="Launch ROI Studio", width=-1, callback=_launch_roi_studio_callback)
            dpg.add_button(label="Hide", tag="hide_button", width=-1, callback=_hide_callback)
            dpg.add_button(label="Exit System", width=-1, callback=_exit_callback)
        dpg.add_loading_indicator(tag="loading_ind", show=False, width=50, indent=75)

    with dpg.window(
        tag="chat_win",
        no_background=False,
        no_move=False,
        no_resize=False,
        no_title_bar=True,
        width=500,
        height=window_height / 2 - 20,
        pos=((window_width / 4), (window_height - 20 - window_height / 2)),
    ):

        if font_is_loaded:
            dpg.bind_item_font(dpg.last_item(), font_arialBold)

        # System Output section title
        dpg.add_separator(label="System Output")
        dpg.add_spacer(height=5)

        # Calculate initial child window sizes (50/50 split)
        parent_initial_height = window_height / 2 - 20
        available_initial_height = parent_initial_height - 150  # Reserve for UI elements
        output_initial_height = int(available_initial_height * 0.50)
        chat_initial_height = int(available_initial_height * 0.50)
        initial_wrap_width = 460

        # Strategy output section
        with dpg.child_window(tag="outputWindow", width=-1, height=output_initial_height, border=True):
            dpg.add_text("", tag="outputText", wrap=initial_wrap_width)
            if font_is_loaded:
                dpg.bind_item_font(dpg.last_item(), font_arial)

        # Chat conversation section
        dpg.add_spacer(height=5)
        dpg.add_separator(label="Chatbox")
        dpg.add_spacer(height=5)
        with dpg.child_window(tag="chatWindow", width=-1, height=chat_initial_height, border=True):
            dpg.add_text("", tag="chatLog", wrap=initial_wrap_width)
            if font_is_loaded:
                dpg.bind_item_font(dpg.last_item(), font_arial)

        # User input area
        dpg.add_spacer(height=5)
        with dpg.group(horizontal=True):
            dpg.add_input_text(tag="chatInput", width=360, hint="Type here to discuss strategy with agent...")
            dpg.add_button(label="Send", width=80, callback=_send_message)

    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 6, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 6, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 5, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, 16, category=dpg.mvThemeCat_Core)

    # Store theme globally for popup access
    global_theme_ref = global_theme

    with dpg.theme() as mini_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 4, 4)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0, category=dpg.mvThemeCat_Core)

    dpg.bind_item_theme("buttons_container", global_theme)
    dpg.bind_item_theme("chat_win", global_theme)

    # Stats window
    with dpg.window(
        tag="stats_window",
        no_background=False,
        no_move=False,
        no_resize=False,
        no_title_bar=True,
        width=(window_width / 7),
        height=635,
        pos=((window_width * 2 / 3), (window_height / 4)),
    ):
        if font_is_loaded:
            dpg.bind_item_font(dpg.last_item(), font_arialBold)

        dpg.add_text("Stats")
        dpg.add_text("Total Phases: ", indent=10, tag="Total_phases")
        if font_is_loaded:
            dpg.bind_item_font(dpg.last_item(), font_arial)
        dpg.bind_item_theme(dpg.last_item(), mini_theme)
        dpg.add_text("Total Actions: ", indent=10, tag="Total_actions")
        if font_is_loaded:
            dpg.bind_item_font(dpg.last_item(), font_arial)
        dpg.bind_item_theme(dpg.last_item(), mini_theme)

        dpg.add_separator(label="Phase 1")
        with dpg.child_window(height=155):
            if font_is_loaded:
                dpg.bind_item_font(dpg.last_item(), font_arial)
            with dpg.table(header_row=True, row_background=True, borders_innerV=True):
                dpg.add_table_column(width_fixed=True, width=100)
                dpg.add_table_column(label="Blue")
                dpg.add_table_column(label="Red")
                dpg.add_table_column(label="Difference")

                with dpg.table_row():
                    dpg.add_text("Units Remaining")
                    dpg.add_text("", tag="P1_Blue_units")
                    dpg.add_text("", tag="P1_Red_units")
                    dpg.add_text("", tag="P1_Diff_units")

                with dpg.table_row():
                    dpg.add_text("Units Lost")
                    dpg.add_text("", tag="P1_Blue_lost")
                    dpg.add_text("", tag="P1_Red_lost")
                    dpg.add_text("", tag="P1_Diff_lost")

                with dpg.table_row():
                    dpg.add_text("Bases Controlled")
                    dpg.add_text("", tag="P1_Blue_bases")
                    dpg.add_text("", tag="P1_Red_bases")
                    dpg.add_text("", tag="P1_Diff_bases")

                with dpg.table_row():
                    dpg.add_text("Actions Taken")
                    dpg.add_text("", tag="P1_Blue_actions")
                    dpg.add_text("")
                    dpg.add_text("")

        dpg.add_separator(label="Phase 2")
        with dpg.child_window(height=155):
            if font_is_loaded:
                dpg.bind_item_font(dpg.last_item(), font_arial)
            with dpg.table(header_row=True, row_background=True, borders_innerV=True):
                dpg.add_table_column(width_fixed=True, width=100)
                dpg.add_table_column(label="Blue")
                dpg.add_table_column(label="Red")
                dpg.add_table_column(label="Difference")

                with dpg.table_row():
                    dpg.add_text("Units Remaining")
                    dpg.add_text("", tag="P2_Blue_units")
                    dpg.add_text("", tag="P2_Red_units")
                    dpg.add_text("", tag="P2_Diff_units")

                with dpg.table_row():
                    dpg.add_text("Units Lost")
                    dpg.add_text("", tag="P2_Blue_lost")
                    dpg.add_text("", tag="P2_Red_lost")
                    dpg.add_text("", tag="P2_Diff_lost")

                with dpg.table_row():
                    dpg.add_text("Bases Controlled")
                    dpg.add_text("", tag="P2_Blue_bases")
                    dpg.add_text("", tag="P2_Red_bases")
                    dpg.add_text("", tag="P2_Diff_bases")

                with dpg.table_row():
                    dpg.add_text("Actions Taken")
                    dpg.add_text("", tag="P2_Blue_actions")
                    dpg.add_text("")
                    dpg.add_text("")

        dpg.add_separator(label="Phase 3")
        with dpg.child_window(height=155):
            if font_is_loaded:
                dpg.bind_item_font(dpg.last_item(), font_arial)
            with dpg.table(header_row=True, row_background=True, borders_innerV=True):
                dpg.add_table_column(width_fixed=True, width=100)
                dpg.add_table_column(label="Blue")
                dpg.add_table_column(label="Red")
                dpg.add_table_column(label="Difference")

                with dpg.table_row():
                    dpg.add_text("Units Remaining")
                    dpg.add_text("", tag="P3_Blue_units")
                    dpg.add_text("", tag="P3_Red_units")
                    dpg.add_text("", tag="P3_Diff_units")

                with dpg.table_row():
                    dpg.add_text("Units Lost")
                    dpg.add_text("", tag="P3_Blue_lost")
                    dpg.add_text("", tag="P3_Red_lost")
                    dpg.add_text("", tag="P3_Diff_lost")

                with dpg.table_row():
                    dpg.add_text("Bases Controlled")
                    dpg.add_text("", tag="P3_Blue_bases")
                    dpg.add_text("", tag="P3_Red_bases")
                    dpg.add_text("", tag="P3_Diff_bases")

                with dpg.table_row():
                    dpg.add_text("Actions Taken")
                    dpg.add_text("", tag="P3_Blue_actions")
                    dpg.add_text("")
                    dpg.add_text("")

        dpg.child_window()

    dpg.bind_item_theme("stats_window", global_theme)

    # Start background thread for dynamic resizing
    resize_thread = threading.Thread(target=_update_chat_window_sizes, daemon=True)
    resize_thread.start()

    # Style editor for real-time experimentation (positioned top-right) - COMMENTED OUT
    # with dpg.window(tag="style_editor_win", no_background=False, no_move=False, no_resize=False, no_title_bar=True,
    #                 width=300, height=200,
    #                 pos=(window_width - 320, 20),
    #                 show=False):  # Hidden by default
    #     dpg.add_text("Style Editor Controls")
    #     dpg.add_button(label="Show Style Editor", callback=lambda: dpg.show_tool(dpg.mvTool_Style))
    #     dpg.add_button(label="Show Metrics", callback=lambda: dpg.show_tool(dpg.mvTool_Metrics))
    #     dpg.add_button(label="Toggle This Panel", callback=lambda: dpg.configure_item("style_editor_win", show=not dpg.is_item_shown("style_editor_win")))

    # Toggle button for style editor (top-right corner) - COMMENTED OUT
    # with dpg.window(tag="style_toggle_win", no_background=False, no_move=False, no_resize=True, no_title_bar=True,
    #                 width=80, height=30,
    #                 pos=(window_width - 90, 10)):
    #     dpg.add_button(label="Styles", width=70, height=20,
    #                   callback=lambda: dpg.configure_item("style_editor_win", show=not dpg.is_item_shown("style_editor_win")))


# Theme system implementation complete - using targeted themes for specific components


# MARK: Callbacks
def _generation_callback(sender, app_data, user_data):
    """Handles button press response of \"Generate Strategy\"

    Called on button press"""
    global running

    print("Generate Strategy button pressed")

    # Set UI to running state
    running = True
    _change_ui_state(True)

    # Start the save state check flow
    _start_save_state_check()


def _stopButton_callback(sender, app_data, user_data):
    """Cancel button - stops current operation"""
    global running, current_subprocess, current_agent_subprocess

    print("CANCEL BUTTON PRESSED")
    running = False  # Stop all loops

    # Close any open popups
    if dpg.does_item_exist("save_state_popup"):
        dpg.delete_item("save_state_popup")
        print("Closed save_state popup")
    if dpg.does_item_exist("phase_selection_popup"):
        dpg.delete_item("phase_selection_popup")
        print("Closed phase_selection popup")

    # Update chatbox
    dpg.set_value("outputText", "Cancelling operation...")

    # Terminate all active subprocesses
    # 1. Screen reading subprocess (LIVE_GAME_READER)
    if current_subprocess:
        try:
            if current_subprocess.poll() is None:  # Still running
                print(f"Terminating screen reading subprocess PID: {current_subprocess.pid}")
                terminate_process_tree_aggressive(current_subprocess.pid)
        except Exception as e:
            print(f"Error terminating screen reading subprocess: {e}")
        current_subprocess = None

    # 2. Agent strategy generation subprocess
    if current_agent_subprocess:
        try:
            if current_agent_subprocess.poll() is None:  # Still running
                print(f"Terminating agent subprocess PID: {current_agent_subprocess.pid}")
                terminate_process_tree_aggressive(current_agent_subprocess.pid)
        except Exception as e:
            print(f"Error terminating agent subprocess: {e}")
        current_agent_subprocess = None

    # Clean up progress file
    try:
        progress_file = os.path.join("agent", "screen_reading", "output", "progress.json")
        if os.path.exists(progress_file):
            os.remove(progress_file)
            print("Progress file removed")
    except Exception as e:
        print(f"Error cleaning up progress file: {e}")

    # Reset UI state
    _change_ui_state(False)
    dpg.set_value("outputText", "Operation cancelled\n\nReady for new operation...")
    print("Cancel completed")


def _launch_roi_studio_callback(sender, app_data, user_data):
    """Launches the ROI Studio application

    Called on \"Launch ROI Studio\" button press"""
    try:
        print("Launching ROI Studio...")
        # Get the project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        roi_studio_path = os.path.join(project_root, "screen_reading", "LIVE_ROI_STUDIO.py")

        # Launch ROI Studio as a separate process
        subprocess.Popen([sys.executable, roi_studio_path], cwd=project_root)
        print(f"ROI Studio launched from: {roi_studio_path}")
    except Exception as e:
        print(f"Failed to launch ROI Studio: {e}")


def _hide_callback(sender, app_data, user_data):
    global hidden
    if hidden == False:
        hidden = True
        dpg.set_item_label(sender, "Show")
        dpg.hide_item("chat_win")
        dpg.hide_item("stats_window")
    else:
        hidden = False
        dpg.show_item("chat_win")
        dpg.show_item("stats_window")
        dpg.set_item_label(sender, "Hide")


def _exit_callback(sender, app_data, user_data):
    """Exit System button - shuts down everything and exits"""
    global overlay_instance, running, current_subprocess, current_agent_subprocess
    print("EXIT SYSTEM BUTTON PRESSED")

    running = False  # Stop all loops

    # Close any open popups
    if dpg.does_item_exist("save_state_popup"):
        dpg.delete_item("save_state_popup")
    if dpg.does_item_exist("phase_selection_popup"):
        dpg.delete_item("phase_selection_popup")

    try:
        dpg.set_value("outputText", "EXITING: Shutting down...")
    except:
        pass

    # Terminate any running subprocesses
    if current_subprocess:
        try:
            if current_subprocess.poll() is None:
                print(f"Terminating subprocess PID: {current_subprocess.pid}")
                terminate_process_tree_aggressive(current_subprocess.pid)
        except:
            pass

    if current_agent_subprocess:
        try:
            if current_agent_subprocess.poll() is None:
                print(f"Terminating agent subprocess PID: {current_agent_subprocess.pid}")
                terminate_process_tree_aggressive(current_agent_subprocess.pid)
        except:
            pass

    # Kill any remaining LIVE_GAME_READER processes
    try:
        selective_shutdown()
        print("Selective shutdown completed")
    except:
        pass

    # Start delayed nuclear cleanup in background
    try:
        nuclear_shutdown_delayed()
    except:
        pass

    # Stop overlay
    try:
        if overlay_instance:
            overlay_instance.stop()
    except:
        pass

    # Stop DearPyGUI
    try:
        dpg.stop_dearpygui()
    except:
        pass

    # Force exit
    print("Exiting...")
    os._exit(0)


# MARK: Chat Callbacks


def _send_message():
    user_msg = dpg.get_value("chatInput").strip()
    if not user_msg:
        return

    dpg.set_value("chatInput", "")

    current_log = dpg.get_value("chatLog")
    dpg.set_value("chatLog", f"{current_log}\n\nYou: {user_msg}\n\nAgent: Thinking...")

    # Process in background to avoid blocking UI
    threading.Thread(target=_process_chat_message, args=(user_msg,)).start()


def _process_chat_message(user_question):
    try:
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        agent_dir = project_root / "agent" / "decision_logic" / "run_agent"
        game_state_dir = agent_dir / "game_state"

        json_files = list(game_state_dir.glob("*.json"))

        if not json_files:
            raise FileNotFoundError("No game state JSON found. Generate a strategy first.")

        latest_json = max(json_files, key=lambda p: p.stat().st_mtime)
        json_filename = latest_json.name

        # Use blocking subprocess.run() - chat is independent and not cancellable
        result = subprocess.run(
            [sys.executable, "chat_discuss_cli.py", json_filename, user_question],
            cwd=str(agent_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise Exception(f"Chat subprocess failed: {result.stderr or 'Unknown error'}")

        answer = result.stdout.strip()

        if not answer:
            raise Exception("No response from chat system")

        current_log = dpg.get_value("chatLog")
        updated = current_log.replace("Agent: Thinking...", f"Agent: {answer}")
        _safe_dpg_call(dpg.set_value, "chatLog", updated)

    except Exception as e:
        current_log = dpg.get_value("chatLog")
        updated = current_log.replace("Agent: Thinking...", f"Agent: Error - {str(e)}")
        _safe_dpg_call(dpg.set_value, "chatLog", updated)


# MARK: Callbacks end


def _update_chat_window_sizes():
    # Background thread for dynamic window resizing
    while True:
        try:
            if not dpg.does_item_exist("chat_win"):
                time.sleep(0.1)
                continue

            parent_width = dpg.get_item_width("chat_win")
            parent_height = dpg.get_item_height("chat_win")

            # Reserve space for UI elements (150px)
            available_height = parent_height - 150
            if available_height < 150:
                available_height = 150

            # Split 50/50 for equal sizing
            output_height = int(available_height * 0.50)
            chat_height = int(available_height * 0.50)

            # Calculate wrap width (parent - scrollbar/padding)
            wrap_width = int(parent_width - 40)
            if wrap_width < 200:
                wrap_width = 200

            # Calculate input width (Send button stays fixed at 80px)
            input_width = int(parent_width - 130)
            if input_width < 200:
                input_width = 200

            dpg.configure_item("outputWindow", height=output_height)
            dpg.configure_item("chatWindow", height=chat_height)
            dpg.configure_item("outputText", wrap=wrap_width)
            dpg.configure_item("chatLog", wrap=wrap_width)
            dpg.configure_item("chatInput", width=input_width)

        except Exception:
            pass  # Items may not exist during initialisation

        time.sleep(0.1)  # Poll every 100ms


def _start_save_state_check():
    """Check for save_state.json and show popup if not found"""
    # Get project root path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    save_state_path = os.path.join(project_root, "save_state.json")

    # Check if save_state.json exists
    if os.path.exists(save_state_path):
        print("save_state.json found - no popup needed")
        # Launch subprocess in worker thread so main thread stays responsive
        thread = threading.Thread(target=_launch_subprocess_with_phase_selection, args=(None,), daemon=True)
        thread.start()
    else:
        # save_state.json not found - show popup (on main thread - safe)
        print("save_state.json not found - showing popup...")
        dpg.set_value("outputText", "Save state not found. Please see popup window...")
        _show_save_state_popup()


def _show_save_state_popup():
    """Create and show save state popup inline"""
    # Clean up existing popup if it exists
    if dpg.does_item_exist("save_state_popup"):
        dpg.delete_item("save_state_popup")

    # Create popup window directly
    with dpg.window(
        label="Save State Not Found",
        modal=False,
        show=True,
        tag="save_state_popup",
        no_resize=True,
        no_move=True,
        width=500,
        height=200,
        pos=(400, 300),
    ):
        dpg.add_text(
            "save_state.json not found in project root.\n\n"
            "Please save your simulation in RTSViewer as 'save_state.json'\n"
            "in the project root directory for enriched game state export.\n\n"
            "Click 'Retry' after saving, or 'Skip' to proceed without."
        )
        # Apply font to text if available
        if font_arial_global:
            dpg.bind_item_font(dpg.last_item(), font_arial_global)

        dpg.add_separator()

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Retry (Check Again)",
                width=200,
                callback=_on_retry_button_clicked,
            )
            dpg.add_button(
                label="Skip (Proceed Without)",
                width=200,
                callback=_on_skip_button_clicked,
            )

    # Apply global theme and font to popup window
    if global_theme_ref:
        dpg.bind_item_theme("save_state_popup", global_theme_ref)
    if font_arial_global:
        dpg.bind_item_font("save_state_popup", font_arial_global)


def _on_retry_button_clicked():
    """Retry button callback - checks for file, closes popup if found"""
    print("User clicked Retry - checking for save_state.json...")

    # Get project root path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    save_state_path = os.path.join(project_root, "save_state.json")

    # Check if save_state.json exists now
    if os.path.exists(save_state_path):
        # File found! Close popup and proceed
        print("save_state.json found - proceeding...")
        dpg.set_value("outputText", "Save state found! Starting screen reading...")
        dpg.delete_item("save_state_popup")
        # Launch subprocess in worker thread so main thread stays responsive
        thread = threading.Thread(target=_launch_subprocess_with_phase_selection, args=(None,), daemon=True)
        thread.start()
    else:
        # Still not found - update message, keep popup open
        print("save_state.json still not found - popup remains open...")
        dpg.set_value("outputText", "Save state not found. Please save file and click Retry...")


def _on_skip_button_clicked():
    """Skip button callback - closes save state popup, shows phase selection"""
    print("User clicked Skip - showing phase selection popup...")
    dpg.delete_item("save_state_popup")
    dpg.set_value("outputText", "Please select which phase has no actions...")
    _show_phase_selection_popup()


def _show_phase_selection_popup():
    """Create and show phase selection popup inline"""
    # Clean up existing popup if it exists
    if dpg.does_item_exist("phase_selection_popup"):
        dpg.delete_item("phase_selection_popup")

    # Create popup window directly
    with dpg.window(
        label="Phase Selection Required",
        modal=False,
        show=True,
        tag="phase_selection_popup",
        no_resize=True,
        no_move=True,
        width=550,
        height=280,
        pos=(400, 300),
    ):
        dpg.add_text(
            "Unable to detect save_state.json for automatic phase detection.\n\n"
            "Please select the next phase with NO action cards:\n"
            "(This helps determine which phases need OCR processing)\n"
        )
        # Apply font to descriptive text
        if font_arial_global:
            dpg.bind_item_font(dpg.last_item(), font_arial_global)

        dpg.add_separator()

        dpg.add_text("\nWhat is the next phase with NO action cards?", color=(255, 200, 100))
        # Apply font to highlighted question text
        if font_arial_global:
            dpg.bind_item_font(dpg.last_item(), font_arial_global)

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Phase 1 (No Actions)",
                width=160,
                callback=lambda: _on_phase_selected(1),
            )
            dpg.add_button(
                label="Phase 2 (No Actions)",
                width=160,
                callback=lambda: _on_phase_selected(2),
            )
            dpg.add_button(
                label="Phase 3 (No Actions)",
                width=160,
                callback=lambda: _on_phase_selected(3),
            )

        dpg.add_separator()

        dpg.add_button(
            label="All Phases Have Actions",
            width=250,
            callback=lambda: _on_phase_selected(0),
        )

    # Apply global theme and font to popup window (includes title bar and buttons)
    if global_theme_ref:
        dpg.bind_item_theme("phase_selection_popup", global_theme_ref)
    if font_arial_global:
        dpg.bind_item_font("phase_selection_popup", font_arial_global)


def _on_phase_selected(phase_num: int):
    """Phase selection button callback - closes popup and launches subprocess"""
    print(f"User selected: Phase {phase_num} has no actions")
    dpg.delete_item("phase_selection_popup")
    # Launch subprocess in worker thread so main thread stays responsive
    thread = threading.Thread(target=_launch_subprocess_with_phase_selection, args=(phase_num,), daemon=True)
    thread.start()


def _launch_subprocess_with_phase_selection(phase_selection: Optional[int]):
    # Launch LIVE_GAME_READER subprocess with optional phase selection and monitor progress
    # phase_selection: None if save_state.json exists, or 0-3 from user popup
    global current_subprocess, current_process, running

    current_process = None
    current_subprocess = None

    # Now display warning message
    warning_msg = "=== IMPORTANT: DO NOT MOVE MOUSE ===\n"
    warning_msg += "Screen reading in progress...\n"
    warning_msg += "To stop: Use 'Cancel' or 'Exit System' buttons\n"
    warning_msg += "\nStarting screen reading process..."
    _safe_dpg_call(dpg.set_value, "outputText", warning_msg)

    # Path to progress file (relative to screen_reading directory)
    progress_file = os.path.join("agent", "screen_reading", "output", "progress.json")

    # Clear any stale progress file
    if os.path.exists(progress_file):
        try:
            os.remove(progress_file)
            print(f"Cleared stale progress file: {progress_file}")
        except Exception as e:
            print(f"Failed to clear progress file: {e}")

    # Run screen reading in a separate thread
    thread = threading.Thread(target=_run_agent, args=(phase_selection,))
    thread.start()

    # Monitor progress file and update UI (on main thread for DPG compatibility)
    agent_launched = False  # Track if agent bridge was launched
    last_status = ""

    while thread.is_alive():
        if not running:
            # User cancelled or exiting - thread will detect this and clean up
            break

        # Check if DPG is still running (exit may have been called)
        if not dpg.is_dearpygui_running():
            print("DPG shutting down - exiting progress monitor")
            break

        # Try to read progress file
        try:
            if os.path.exists(progress_file):
                with open(progress_file, "r") as f:
                    progress_data = json.load(f)
                    current_status = progress_data.get("status", "")

                    # Only update if status changed
                    if current_status != last_status:
                        last_status = current_status
                        phase = progress_data.get("phase", 0)
                        percentage = progress_data.get("percentage", 0)

                        # Format the display message - show warning only during capture phase
                        # Remove warning once captures complete (percentage >= 80 or status mentions OCR)
                        if (
                            percentage >= 80
                            or "processing ocr" in current_status.lower()
                            or "ocr processing" in current_status.lower()
                            or "screenshots captured" in current_status.lower()
                        ):
                            display_text = "=== CAPTURES COMPLETE ===\n"
                            display_text += "Processing OCR - You can move your mouse now\n\n"
                        else:
                            display_text = "=== DO NOT MOVE MOUSE ===\n"
                            display_text += "Use Cancel or Exit System if needed\n\n"

                        if percentage > 0:
                            display_text += f"[{percentage}%] "

                        display_text += current_status

                        if phase > 0:
                            display_text += f" (Phase {phase}/3)"

                        # Thread-safe UI update (running in worker thread)
                        try:
                            dpg.split_frame()  # Ensure thread-safe UI updates
                            dpg.set_value("outputText", display_text)
                        except:
                            pass  # DPG may be shutting down

                    # Check if complete
                    if progress_data.get("complete", False):
                        try:
                            dpg.split_frame()  # Ensure thread-safe UI updates
                            dpg.set_value(
                                "outputText",
                                f"COMPLETE: {current_status}\n\nStarting strategy generation...",
                            )
                        except:
                            pass  # DPG may be shutting down

                        # Wait for thread to finish
                        thread.join(timeout=2)

                        # Call agent to generate strategy
                        agent_launched = _call_agent_for_strategy()
                        break

                    # Check for errors
                    if progress_data.get("error", False):
                        try:
                            dpg.split_frame()  # Ensure thread-safe UI updates
                            dpg.set_value("outputText", f"ERROR: {current_status}")
                        except:
                            pass  # DPG may be shutting down
                        break

        except (FileNotFoundError, json.JSONDecodeError):
            pass  # Progress file not ready yet

        time.sleep(0.5)  # Check every half second

    # Wait for thread to complete
    thread.join(timeout=1)

    # Only reset UI state if agent was not launched (agent will manage its own state)
    if not agent_launched and running:
        running = False
        _change_ui_state(False)


def _call_agent_for_strategy():
    # Run agent strategy generation in a separate thread to avoid blocking UI
    thread = threading.Thread(target=_run_agent_strategy)
    thread.start()
    return True  # Agent successfully launched


def _run_agent_strategy():
    global current_agent_subprocess, running

    # Set UI state to running for agent execution
    running = True
    _change_ui_state(True)

    # Generate strategy using the agent bridge
    try:
        _safe_dpg_call(dpg.set_value, "outputText", "STRATEGY GENERATION: Initialising agent...")

        # Create agent bridge
        bridge = AgentBridge()

        # Update progress
        _safe_dpg_call(dpg.set_value, "outputText", "STRATEGY GENERATION: Bridging game state to agent...")

        # Create process holder list to track subprocess (passed by reference)
        process_holder = [None]

        # Generate strategy (auto-detects enriched vs simple based on what LIVE_GAME_READER created)
        # Pass process_holder so AgentBridge can store subprocess reference
        success, result = bridge.generate_strategy(process_holder=process_holder)

        # Store subprocess in global for cancel button access
        if process_holder[0] is not None:
            current_agent_subprocess = process_holder[0]

        # Check if operation was cancelled during execution
        if not running:
            print("Agent strategy generation was cancelled")
            _safe_dpg_call(dpg.set_value, "outputText", "Operation cancelled\n\nReady for new operation...")
            return

        if success:
            # Strategy generated successfully - display it only if still running
            if running:
                _safe_dpg_call(dpg.set_value, "outputText", f"STRATEGY GENERATED:\n\n{result}")
                _safe_dpg_call(dpg.set_value, "chatLog", "Strategy ready! Ask questions about it.")
                print("Strategy generation completed successfully")

                # Update stats panel with latest game statistics
                _display_stats()
        else:
            # Error occurred - display only if still running
            if running:
                _safe_dpg_call(
                    dpg.set_value,
                    "outputText",
                    f"STRATEGY GENERATION FAILED:\n\n{result or 'Unknown error occurred'}",
                )
                print(f"Strategy generation failed: {result}")

    except Exception as e:
        error_msg = f"Error in strategy generation: {str(e)}"
        if running:  # Only display error if not cancelled
            _safe_dpg_call(dpg.set_value, "outputText", f"STRATEGY GENERATION ERROR:\n\n{error_msg}")
        print(error_msg)

    # Reset UI state when done
    running = False
    current_agent_subprocess = None
    _change_ui_state(False)


def _display_stats():
    """Update stats panel with latest game statistics.

    Called from worker thread after strategy generation completes.
    Uses direct dpg.set_value() calls matching existing _run_agent_strategy() pattern.
    """
    try:
        the_stats = stats.stats_processing()

        if not the_stats:
            print("No stats data returned from stats_processing()")
            return

        total_phases = the_stats[0]
        total_actions = the_stats[1]

        # Update summary stats
        _safe_dpg_call(dpg.set_value, "Total_phases", f"Total Phases: {total_phases}")
        _safe_dpg_call(dpg.set_value, "Total_actions", f"Total Actions: {total_actions}")

        # Update Phase 1 if exists
        if total_phases >= 1 and len(the_stats) > 2:
            phase_stats = the_stats[2]
            _safe_dpg_call(dpg.set_value, "P1_Blue_units", phase_stats[0][0])
            _safe_dpg_call(dpg.set_value, "P1_Red_units", phase_stats[1][0])
            _safe_dpg_call(dpg.set_value, "P1_Diff_units", phase_stats[2][0])
            _safe_dpg_call(dpg.set_value, "P1_Blue_lost", phase_stats[0][1])
            _safe_dpg_call(dpg.set_value, "P1_Red_lost", phase_stats[1][1])
            _safe_dpg_call(dpg.set_value, "P1_Diff_lost", phase_stats[2][1])
            _safe_dpg_call(dpg.set_value, "P1_Blue_actions", phase_stats[0][2])
            _safe_dpg_call(dpg.set_value, "P1_Blue_bases", phase_stats[0][3])
            _safe_dpg_call(dpg.set_value, "P1_Red_bases", phase_stats[1][3])
            _safe_dpg_call(dpg.set_value, "P1_Diff_bases", phase_stats[2][3])

        # Update Phase 2 if exists
        if total_phases >= 2 and len(the_stats) > 3:
            phase_stats = the_stats[3]
            _safe_dpg_call(dpg.set_value, "P2_Blue_units", phase_stats[0][0])
            _safe_dpg_call(dpg.set_value, "P2_Red_units", phase_stats[1][0])
            _safe_dpg_call(dpg.set_value, "P2_Diff_units", phase_stats[2][0])
            _safe_dpg_call(dpg.set_value, "P2_Blue_lost", phase_stats[0][1])
            _safe_dpg_call(dpg.set_value, "P2_Red_lost", phase_stats[1][1])
            _safe_dpg_call(dpg.set_value, "P2_Diff_lost", phase_stats[2][1])
            _safe_dpg_call(dpg.set_value, "P2_Blue_actions", phase_stats[0][2])
            _safe_dpg_call(dpg.set_value, "P2_Blue_bases", phase_stats[0][3])
            _safe_dpg_call(dpg.set_value, "P2_Red_bases", phase_stats[1][3])
            _safe_dpg_call(dpg.set_value, "P2_Diff_bases", phase_stats[2][3])

        # Update Phase 3 if exists
        if total_phases >= 3 and len(the_stats) > 4:
            phase_stats = the_stats[4]
            _safe_dpg_call(dpg.set_value, "P3_Blue_units", phase_stats[0][0])
            _safe_dpg_call(dpg.set_value, "P3_Red_units", phase_stats[1][0])
            _safe_dpg_call(dpg.set_value, "P3_Diff_units", phase_stats[2][0])
            _safe_dpg_call(dpg.set_value, "P3_Blue_lost", phase_stats[0][1])
            _safe_dpg_call(dpg.set_value, "P3_Red_lost", phase_stats[1][1])
            _safe_dpg_call(dpg.set_value, "P3_Diff_lost", phase_stats[2][1])
            _safe_dpg_call(dpg.set_value, "P3_Blue_actions", phase_stats[0][2])
            _safe_dpg_call(dpg.set_value, "P3_Blue_bases", phase_stats[0][3])
            _safe_dpg_call(dpg.set_value, "P3_Red_bases", phase_stats[1][3])
            _safe_dpg_call(dpg.set_value, "P3_Diff_bases", phase_stats[2][3])

        print("Stats panel updated successfully")

    except Exception as e:
        print(f"Error updating stats panel: {e}")
        import traceback

        traceback.print_exc()


def _safe_dpg_call(func, *args, **kwargs):
    """Thread-safe wrapper for ANY DPG function called from worker threads.

    Uses dpg.split_frame() to synchronise with DPG's render loop.
    Prevents UI corruption when updating from background threads.
    """
    try:
        if not dpg.is_dearpygui_running():
            return
        dpg.split_frame()  # Sync with DPG render thread
        return func(*args, **kwargs)
    except Exception as e:
        print(f"Error in thread-safe DPG call: {e}")
        return None


def _change_ui_state(running):
    """Changes the ui state depending on wether the agent is currently running or not."""
    if running:
        dpg.disable_item("agent_button")
        dpg.enable_item("cancel_button")
        dpg.show_item("loading_ind")
    else:
        dpg.enable_item("agent_button")
        dpg.disable_item("cancel_button")
        dpg.hide_item("loading_ind")


def _run_agent(phase_selection: Optional[int] = None):
    """This function runs the LIVE_GAME_READER process.
    This will be called as a separate thread.

    Launches LIVE_GAME_READER.py and captures its output.

    Args:
        phase_selection: None if save_state.json exists, or 0-3 from user popup"""
    global current_subprocess, running
    try:
        # Get the screen_reading directory (LIVE_GAME_READER needs to run from here to find ROI files)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        screen_reading_dir = os.path.join(project_root, "agent", "screen_reading")
        game_reader_path = os.path.join(screen_reading_dir, "LIVE_GAME_READER.py")

        print(f"Launching LIVE_GAME_READER from: {game_reader_path}")
        print(f"Working directory: {screen_reading_dir}")

        # Build command with phase selection if needed
        cmd = [sys.executable, "LIVE_GAME_READER.py"]

        # Add phase selection argument if provided
        if phase_selection is not None:
            cmd.extend(["--phase-selection", str(phase_selection)])
            print(f"Passing --phase-selection {phase_selection} to LIVE_GAME_READER")

        # Run LIVE_GAME_READER as subprocess with screen_reading as working directory
        current_subprocess = subprocess.Popen(
            cmd,
            cwd=screen_reading_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for completion while checking for cancellation
        stdout_data = ""
        stderr_data = ""

        try:
            stdout_data, stderr_data = current_subprocess.communicate(timeout=300)  # 5 minute timeout
            result_returncode = current_subprocess.returncode
        except subprocess.TimeoutExpired:
            if running:  # Only kill if not already cancelled
                current_subprocess.kill()
                stdout_data, stderr_data = current_subprocess.communicate()
            result_returncode = -1

        # Prepare output for display
        output_text = ""
        if stdout_data:
            output_text += "STDOUT:\n" + stdout_data + "\n\n"
        if stderr_data:
            output_text += "STDERR:\n" + stderr_data + "\n\n"

        output_text += f"Exit Code: {result_returncode}\n"

        if result_returncode == 0:
            output_text += "SUCCESS: Game reading completed"
        elif result_returncode == -1:
            output_text += "TIMEOUT: Game reading timed out"
        else:
            output_text += "FAILED: Game reading failed"

        # Write output to file for UI to read
        output_file = os.path.join(os.path.dirname(__file__), "finalOutput.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output_text)

    except subprocess.TimeoutExpired:
        output_text = "ERROR: LIVE_GAME_READER timed out after 5 minutes"
        output_file = os.path.join(os.path.dirname(__file__), "finalOutput.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output_text)
    except Exception as e:
        output_text = f"ERROR: Failed to launch LIVE_GAME_READER: {str(e)}"
        output_file = os.path.join(os.path.dirname(__file__), "finalOutput.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output_text)
