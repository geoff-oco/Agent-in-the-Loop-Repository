import dearpygui.dearpygui as dpg
import threading
import time
import psutil
import win32gui
import win32process


running = False

def ui(tar_hwnd=None):
    '''Function that describes the UI layout and functionality to dearPyGui'''

    with dpg.window(tag="buttons_win", no_background=False, no_move=False, no_resize=True, no_title_bar=True, width=200, height=110):
        with dpg.group(tag="agent_button"):
            dpg.add_button(label='Generate Strategy', width=-1, callback=_generation_callback)
        with dpg.group(tag="cancel_button",enabled=False):
            dpg.add_button(label="Cancel", width=-1,callback=_stopButton_callback)
        dpg.add_loading_indicator(tag="loading_ind",show=False,width=50,indent=75)

    with dpg.window(tag="chat_win", no_background=False, no_move=False, no_resize=False, no_title_bar=True, width=500,height=400):
        dpg.add_separator(label='Output')
        with dpg.child_window(tag='outputWindow'):
            dpg.add_text('',tag="outputText", wrap= 490)

"""     with dpg.theme() as global_theme:
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3, category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.myStyleVar_FramePadding, (8,6), category=dpg.mvThemeCat_Core)

    dpg.bind_theme(global_theme) """


def _generation_callback(sender, app_data, user_data):
    '''Handles button press response of \"Generate Strategy\"
    
        Called on  button press'''
    
    print("button was pressed")

    thread = threading.Thread(target=_run_agent)
    thread.start()


def _stopButton_callback(sender, app_data, user_data):
    '''Stops Agent by setting running flag to False
    
    Called on \"Cancel\" button press'''
    global running
    running = False
    print("canceling generation")



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


def _run_agent():
    '''Function that runs the agent.
    
        Currently uses a timer to simulate the agent.'''
    with open("agent/visualisation/strategyExample.txt") as file:
        global running
        running = True
        _change_ui_state(running)

        for i in range(70):
            if running:
                time.sleep(0.05)
            else:
                break

        if running:
            file.seek(0)
            dpg.set_value("outputText",file.read())

        
        running = False
        _change_ui_state(running)



