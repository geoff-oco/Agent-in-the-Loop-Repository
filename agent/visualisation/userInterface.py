import dearpygui.dearpygui as dpg

#userInterface
#
#   This file builds the UI for the program. 

#Initial DGP setup.
dpg.create_context()
dpg.create_viewport(title='Agent In the loop', width=600, height=300)


# These are functions that occur on button press/checkpoint press
#----------------------------------------------------------------
def generation_callback(sender, app_data, user_data):
    file.seek(0)
    dpg.set_value("outputText",file.read())
    print("button was pressed")

def transparency_callback(sender, app_data, user_data): # Checkbox is commented out currently
    if dpg.get_value(sender):
        dpg.configure_item("Primary Window", no_background=True)
        print("done")
    else:
        dpg.configure_item("Primary Window", no_background=False)
        print("not done")

#Output section reads from "strategyExample.txt"
file = open("agent/visualisation/strategyExample.txt")


#This section defines the window and its widgets
#-----------------------------------------------
with dpg.window(tag="Primary Window", width=600, height=300):
    dpg.add_text("Agent In the loop")
    with dpg.group(horizontal=True):
        dpg.add_button(label='Generate Strategy',tag='button', callback=generation_callback)
        #dpg.add_checkbox(label="Toggle window Transparancy", callback=transparency_callback)

    dpg.add_separator(label='Output')
    with dpg.child_window(tag='outputWindow'):
        dpg.add_text('',tag="outputText", wrap= 500)


#DearPyGui setting up and building UI
#-------------------------------------
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("Primary Window", True)
dpg.start_dearpygui()
dpg.destroy_context()

file.close()