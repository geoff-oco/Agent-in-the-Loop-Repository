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


running = False
overlay_instance = None

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

    # Main container window for buttons (resizable)
    with dpg.window(tag="buttons_container", no_background=False, no_move=False, no_resize=False, no_title_bar=True,
                    width=220, height=180,
                    pos=(40,(window_height/3))):
        dpg.add_text("System Controls", color=(200, 200, 200))
        # Child window inside for actual button content (makes it resizable)
        with dpg.child_window(tag="buttons_win", width=-1, height=-1):
            with dpg.group(tag="agent_button"):
                dpg.add_button(label='Generate Strategy', width=-1, callback=_generation_callback)
            with dpg.group(tag="cancel_button",enabled=False):
                dpg.add_button(label="Cancel", width=-1,callback=_stopButton_callback)
            dpg.add_loading_indicator(tag="loading_ind",show=False,width=50,indent=75)
            dpg.add_separator()
            dpg.add_button(label="Launch ROI Studio", width=-1, callback=_launch_roi_studio_callback)
            dpg.add_button(label="Exit System", width=-1, callback=_exit_callback)

    with dpg.window(tag="chat_win", no_background=False, no_move=False, no_resize=False, no_title_bar=True,
                    width=500, height= window_height / 3 - 10,
                    pos=((window_width/3), (window_height - 10 - window_height/3))):
        dpg.add_text("Chatbox", color=(200, 200, 200))
        dpg.add_separator()
        with dpg.child_window(tag='outputWindow'):
            dpg.add_text('',tag="outputText", wrap= 475)


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
    '''Stops Agent by setting running flag to False

    Called on \"Cancel\" button press'''
    global running
    running = False
    print("canceling generation")


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
    '''Exits the entire application

    Called on \"Exit\" button press'''
    global overlay_instance
    print("Exiting application...")

    # Signal overlay to stop threads before shutting down DearPyGUI
    if overlay_instance:
        overlay_instance.stop()

    dpg.stop_dearpygui()

    # Kill batch processes using taskkill - more reliable approach
    try:
        # Kill any cmd.exe processes that contain our batch file name
        subprocess.run(['taskkill', '/F', '/IM', 'cmd.exe', '/FI', 'WINDOWTITLE eq Agent-in-the-Loop System Launcher*'],
                      capture_output=True, timeout=3)
    except:
        try:
            # Fallback: kill parent process
            current_pid = os.getpid()
            current_process = psutil.Process(current_pid)
            parent = current_process.parent()
            if parent and 'cmd.exe' in parent.name().lower():
                parent.terminate()
        except:
            pass

    # Force terminate the entire process
    os._exit(0)



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
    '''This function is called as a thread when the Generate Strategy button is pressed 
    
        When this button is pressed, it opens the txt file it will be reading from. If the
        agent has run without being canceled it will print that text onto the output window.
        
        The agent will be run in another process. If the running flag is set
        to false via cancel button press, this process is terminated early.

        This function also manages the ui state changes while running'''
    
    with open("agent/visualisation/finalOutput.txt") as file:
        global running
        running = True
        _change_ui_state(running)

        process = Process(target=_run_agent,daemon=True)

        process.start()
        while process.is_alive():
            if not running:
                process.terminate()
                break

        process.join()
        if running:
            file.seek(0)
            dpg.set_value("outputText",file.read())

        
        running = False
        _change_ui_state(running)


def _run_agent():
    '''This is the function that runs the ORC and Agent, in that order.
        This will be called as a seperate process.

        Contains timer to serve as an example for now.'''
    time.sleep(8)
    