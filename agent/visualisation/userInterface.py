import dearpygui.dearpygui as dpg
import time
import threading

# userInterface
#
#   This file builds the UI for the program. 

#Initial DGP setup.
dpg.create_context()
dpg.create_viewport(title='Agent In the loop', width=600, height=300)

# Global Flags
#------------------
canceling = False
running = False
screenCaptured = False

#----------------------
#   Functions
#----------------------

# --------
# run_agent
#
#   Runs the agent and handles UI dissabling and enabling buttons.
#       Currently has psudo run agent and psudo cancel functionality.
# --------
def run_agent():
    dpg.disable_item("genGroup")
    dpg.disable_item("orcGroup")
    dpg.enable_item("stopGroup")
    dpg.show_item(loadingIndicator)

    global running
    global canceling
    running = True
    for i in range(70):
        if not canceling:
            time.sleep(0.05)
        else:
            running = False
            canceling = False
            break
    
    if running:
        file.seek(0)
        dpg.set_value("outputText",file.read())

    dpg.enable_item("genGroup")
    dpg.enable_item("orcGroup")
    dpg.disable_item("stopGroup")
    dpg.hide_item(loadingIndicator)
    running = False


# --------
# run_orc
#
#   Runs the orc and handles UI dissabling and enabling buttons.
#       Currently has psudo run orc and psudo cancel functionality.
#       Enables the generate button after completion.
# --------
def run_orc():
    dpg.disable_item("genGroup")
    dpg.disable_item("orcGroup")
    dpg.enable_item("stopGroup")
    dpg.show_item(loadingIndicator)

    global running
    global canceling
    global screenCaptured
    running = True
    for i in range(25):
        if not canceling:
            time.sleep(0.05)
        else:
            running = False
            canceling = False
            break
    
    if running:
        screenCaptured = True
    dpg.enable_item("genGroup")
    dpg.enable_item("orcGroup")
    dpg.disable_item("stopGroup")
    dpg.hide_item(loadingIndicator)
    running = False

# These are functions that occur on button press/checkpoint press
#
#   These are run in threads to allow cancel functionality.
#----------------------------------------------------------------
def generation_callback(sender, app_data, user_data):
    print("button was pressed")
    thread = threading.Thread(target=run_agent)
    thread.start()

def stopButton_callback(sender, app_data, user_data):
    global canceling
    canceling = True
    print("canceling generation")

def screenCapture_callback(sender, app_data, user_data):
    print("capturing the screen")
    orcthread = threading.Thread(target=run_orc)
    orcthread.start()
    
    
# currently out of use
""" def transparency_callback(sender, app_data, user_data):
    if dpg.get_value(sender):
        dpg.configure_item("Primary Window", no_background=True)
        print("done")
    else:
        dpg.configure_item("Primary Window", no_background=False)
        print("not done") """

#Output section reads from "strategyExample.txt"
file = open("agent/visualisation/strategyExample.txt")


# This section defines the window and its widgets
#-----------------------------------------------
with dpg.window(tag="Primary Window", width=600, height=300):
    dpg.add_text("Agent In the loop")
    with dpg.group(horizontal=True):
        with dpg.group(tag="genGroup", enabled=False):
            generate_button = dpg.add_button(label='Generate Strategy',callback=generation_callback)
        with dpg.group(tag="stopGroup", enabled=False):
            stop_button = dpg.add_button(label='Stop agent', callback=stopButton_callback)
        with dpg.group(tag="orcGroup"):
            orc_button = dpg.add_button(label='Capture Screen', callback=screenCapture_callback)
        #dpg.add_checkbox(label="Toggle window Transparancy", callback=transparency_callback)
        
    loadingIndicator = dpg.add_loading_indicator(show=False)
    dpg.add_separator(label='Output')
    with dpg.child_window(tag='outputWindow'):
        dpg.add_text('',tag="outputText", wrap= 500)

#add disabled button theme
""" with dpg.theme() as global_theme:
    with dpg.theme_component(dpg.mvAll, enabled_state=False):
        dpg.add_theme_color(dpg.mvThemeCol_Text,(128, 128, 128, 255))
        dpg.add_theme_color(dpg.mvThemeCol_Text,(100, 100, 100, 255)) """


#DearPyGui setting up and building UI
#-------------------------------------

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("Primary Window", True)
dpg.start_dearpygui()
dpg.destroy_context()

file.close()