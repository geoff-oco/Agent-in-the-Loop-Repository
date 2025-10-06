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
from win_termination import terminate_process_tree_aggressive, selective_shutdown, nuclear_shutdown_delayed
from agent_bridge import AgentBridge


running = False
overlay_instance = None
current_process = None
current_subprocess = None
current_agent_subprocess = None

def ui(tar_hwnd=None, overlay=None):
    '''Function that describes the UI layout and functionality to dearPyGui'''

    # Store overlay reference globally for callbacks
    global overlay_instance
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
        except SystemError:
            print("Could not find font... switching to default")
            font_is_loaded = False 
            


    # Main container window for buttons (resizable)
    with dpg.window(tag="buttons_container", no_background=False, no_move=False, no_resize=False, no_title_bar=True,
                    width=220, height=255,
                    pos=(40,(window_height/3))):
        if font_is_loaded: dpg.bind_item_font(dpg.last_item(), font_arialBold)
        dpg.add_text("System Controls", color=(200, 200, 200))
        # Child window inside for actual button content (makes it resizable)
        with dpg.child_window(tag="buttons_win", width=-1, auto_resize_y=True):
            with dpg.group(tag="agent_button"):
                dpg.add_button(label='Generate Strategy', width=-1, callback=_generation_callback)
            with dpg.group(tag="cancel_button",enabled=False):
                dpg.add_button(label="Cancel", width=-1,callback=_stopButton_callback)
            dpg.add_spacer(height=5)
            dpg.add_separator()
            dpg.add_spacer(height=5)
            dpg.add_button(label="Launch ROI Studio", width=-1, callback=_launch_roi_studio_callback)
            dpg.add_button(label="Exit System", width=-1, callback=_exit_callback)
        dpg.add_loading_indicator(tag="loading_ind",show=False,width=50,indent=75)

    with dpg.window(tag="chat_win", no_background=False, no_move=False, no_resize=False, no_title_bar=True,
                    width=500, height= window_height / 3 - 10,
                    pos=((window_width/3), (window_height - 10 - window_height/3))):
        if font_is_loaded: dpg.bind_item_font(dpg.last_item(), font_arialBold)
        dpg.add_text("Chatbox", color=(200, 200, 200))
        dpg.add_separator()
        dpg.add_spacer(height=5)
        with dpg.child_window(tag='outputWindow'):
            dpg.add_text('',tag="outputText", wrap= 475)
            if font_is_loaded: dpg.bind_item_font(dpg.last_item(), font_arial)

    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 6, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 6, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 5, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, 16, category=dpg.mvThemeCat_Core)

    dpg.bind_item_theme("buttons_container",global_theme)
    dpg.bind_item_theme("chat_win",global_theme)


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


def _generation_callback(sender, app_data, user_data):
    '''Handles button press response of \"Generate Strategy\"
    
        Called on  button press'''
    print("button was pressed")
    thread = threading.Thread(target=_generate_button_pressed)
    thread.start()


def _stopButton_callback(sender, app_data, user_data):
    global running, current_process, current_subprocess, current_agent_subprocess
    running = False
    print("IMMEDIATE CANCEL - Using aggressive termination")

    # Update chatbox immediately
    dpg.set_value("outputText", "CANCELLING: Force stopping all processes...")

    # IMMEDIATE aggressive termination - no delays
    if current_subprocess and current_subprocess.poll() is None:
        print(f"Force terminating subprocess PID: {current_subprocess.pid}")
        terminate_process_tree_aggressive(current_subprocess.pid)

    # Terminate agent subprocess if running
    if current_agent_subprocess and current_agent_subprocess.poll() is None:
        print(f"Force terminating agent subprocess PID: {current_agent_subprocess.pid}")
        terminate_process_tree_aggressive(current_agent_subprocess.pid)

    # Use selective shutdown to kill only LIVE_GAME_READER processes
    try:
        selective_shutdown()
    except Exception as e:
        print(f"Error in selective shutdown: {e}")

    # Clean up progress file
    try:
        progress_file = os.path.join("agent", "screen_reading", "output", "progress.json")
        if os.path.exists(progress_file):
            os.remove(progress_file)
    except:
        pass

    # Update chatbox with completion message
    dpg.set_value("outputText", "CANCELLED: All processes terminated (screen reading & strategy generation)\n\nReady for new operation...")

    # Reset UI state
    current_agent_subprocess = None
    _change_ui_state(False)


def _launch_roi_studio_callback(sender, app_data, user_data):
    '''Launches the ROI Studio application

    Called on \"Launch ROI Studio\" button press'''
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


def _exit_callback(sender, app_data, user_data):
    global overlay_instance, running
    print("GRACEFUL SHUTDOWN WITH DELAYED CLEANUP")
    running = False

    try:
        dpg.set_value("outputText", "EXITING: Shutting down gracefully...")
    except:
        pass

    # First do selective shutdown of game processes
    try:
        selective_shutdown()
    except:
        pass

    # Start delayed nuclear cleanup in background
    nuclear_shutdown_delayed()

    # Signal overlay to stop
    try:
        if overlay_instance:
            overlay_instance.stop()
    except:
        pass

    # Stop DearPyGUI gracefully
    try:
        dpg.stop_dearpygui()
    except:
        pass

    # Force exit after a brief moment
    os._exit(0)





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
        dpg.set_value("outputText", "STRATEGY GENERATION: Initialising agent...")

        # Create agent bridge
        bridge = AgentBridge()

        # Update progress
        dpg.set_value("outputText", "STRATEGY GENERATION: Bridging game state to agent...")

        # Generate strategy (using simple path for faster results)
        success, result = bridge.generate_strategy(use_simple_path=True)

        if success:
            # Strategy generated successfully - display it
            dpg.set_value("outputText", f"STRATEGY GENERATED:\n\n{result}")
            print("Strategy generation completed successfully")
        else:
            # Error occurred
            dpg.set_value("outputText", f"STRATEGY GENERATION FAILED:\n\n{result or 'Unknown error occurred'}")
            print(f"Strategy generation failed: {result}")

    except Exception as e:
        error_msg = f"Error in strategy generation: {str(e)}"
        dpg.set_value("outputText", f"STRATEGY GENERATION ERROR:\n\n{error_msg}")
        print(error_msg)

    # Reset UI state when done
    running = False
    current_agent_subprocess = None
    _change_ui_state(False)


def _change_ui_state(running):
    '''Changes the ui state depending on wether the agent is currently running or not.'''
    if running:
        dpg.disable_item("agent_button")
        dpg.enable_item("cancel_button")
        dpg.show_item("loading_ind")
    else:
        dpg.enable_item("agent_button")
        dpg.disable_item("cancel_button")
        dpg.hide_item("loading_ind")


def _generate_button_pressed():
    global running, current_process, current_subprocess, current_agent_subprocess
    running = True
    current_process = None
    current_subprocess = None
    current_agent_subprocess = None
    _change_ui_state(running)

    # Display warning message
    warning_msg = "=== IMPORTANT: DO NOT MOVE MOUSE ===\n"
    warning_msg += "Screen reading in progress...\n"
    warning_msg += "To stop: Use 'Cancel' or 'Exit System' buttons\n"
    warning_msg += "\nStarting screen reading process..."
    dpg.set_value("outputText", warning_msg)

    # Path to progress file (relative to screen_reading directory)
    progress_file = os.path.join("agent", "screen_reading", "output", "progress.json")

    # Clear any stale progress file
    if os.path.exists(progress_file):
        try:
            os.remove(progress_file)
            print(f"Cleared stale progress file: {progress_file}")
        except Exception as e:
            print(f"Warning: Could not clear progress file: {e}")

    agent_launched = False  # Track if agent was launched to avoid UI state reset

    try:
        # Start the process
        current_process = Process(target=_run_agent, daemon=True)
        current_process.start()
        process = current_process

        # Monitor progress file
        last_status = ""
        while process.is_alive():
            if not running:
                process.terminate()
                process.join(timeout=5)  # Wait up to 5 seconds for clean termination
                if process.is_alive():
                    process.kill()  # Force kill if still alive
                dpg.set_value("outputText", "Operation cancelled by user")
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

                            # Format the display message with warning
                            display_text = "=== DO NOT MOVE MOUSE ===\n"
                            display_text += "Use Cancel or Exit System if needed\n\n"

                            if percentage > 0:
                                display_text += f"[{percentage}%] "

                            display_text += current_status

                            if phase > 0:
                                display_text += f" (Phase {phase}/3)"

                            dpg.set_value("outputText", display_text)

                        # Check if complete
                        if progress_data.get("complete", False):
                            dpg.set_value("outputText", f"COMPLETE: {current_status}\n\nStarting strategy generation...")

                            # Call agent to generate strategy
                            agent_launched = _call_agent_for_strategy()
                            break

                        # Check for errors
                        if progress_data.get("error", False):
                            dpg.set_value("outputText", f"ERROR: {current_status}")
                            break

            except (FileNotFoundError, json.JSONDecodeError):
                pass  # Progress file not ready yet

            time.sleep(0.5)  # Check every half second

        process.join()

    except Exception as e:
        dpg.set_value("outputText", f"ERROR: {str(e)}")

    # Only reset UI state if agent was not launched (agent will manage its own state)
    if not agent_launched:
        running = False
        _change_ui_state(running)


def _run_agent():
    '''This function runs the LIVE_GAME_READER process.
        This will be called as a separate process.

        Launches LIVE_GAME_READER.py and captures its output.'''
    global current_subprocess, running
    try:
        # Get the screen_reading directory (LIVE_GAME_READER needs to run from here to find ROI files)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        screen_reading_dir = os.path.join(project_root, "agent", "screen_reading")
        game_reader_path = os.path.join(screen_reading_dir, "LIVE_GAME_READER.py")

        print(f"Launching LIVE_GAME_READER from: {game_reader_path}")
        print(f"Working directory: {screen_reading_dir}")

        # Run LIVE_GAME_READER as subprocess with screen_reading as working directory
        current_subprocess = subprocess.Popen(
            [sys.executable, "LIVE_GAME_READER.py"],
            cwd=screen_reading_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
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
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_text)

    except subprocess.TimeoutExpired:
        output_text = "ERROR: LIVE_GAME_READER timed out after 5 minutes"
        output_file = os.path.join(os.path.dirname(__file__), "finalOutput.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_text)
    except Exception as e:
        output_text = f"ERROR: Failed to launch LIVE_GAME_READER: {str(e)}"
        output_file = os.path.join(os.path.dirname(__file__), "finalOutput.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_text)
    