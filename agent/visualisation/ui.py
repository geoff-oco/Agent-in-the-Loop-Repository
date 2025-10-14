import dearpygui.dearpygui as dpg
import threading
from multiprocessing import Process
import time
import psutil
import win32gui
import win32process
import os
import sys
from pathlib import Path


# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parents[2]  # two levels up from visualisation/
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))


running = False

def ui(tar_hwnd=None, overlay_instance=None):
    '''Function that describes the UI layout and functionality to dearPyGui'''

    # Dont start drawing screen while window is minimised
    while win32gui.IsIconic(tar_hwnd): 
        pass

    time.sleep(0.1)
    start_size = win32gui.GetWindowRect(tar_hwnd)
    window_height = start_size[3] - start_size[1]
    window_width = start_size[2] - start_size[0]

    with dpg.window(tag="buttons_win", no_background=False, no_move=False, no_resize=True, no_title_bar=True,
                    width=200, height=110,
                    pos=(40,(window_height/3))):
        with dpg.group(tag="agent_button"):
            dpg.add_button(label='Generate Strategy', width=-1, callback=_generation_callback)
        with dpg.group(tag="cancel_button",enabled=False):
            dpg.add_button(label="Cancel", width=-1,callback=_stopButton_callback)
        dpg.add_loading_indicator(tag="loading_ind",show=False,width=50,indent=75)

    #Chatbox section - Alexia 
    with dpg.window(tag="chat_win", no_background=False, no_move=False, no_resize=False, no_title_bar=True, 
                    width=600, 
                    height=int(window_height / 2),
                    pos=((window_width/3), (window_height - int(window_height / 2) - 10))):
    
        # Strategy output section
        dpg.add_separator(label="Output")
        with dpg.child_window(tag="outputWindow", width=580, height=150):
            dpg.add_text('', tag="outputText", wrap=560)
        
        # Chat section
        dpg.add_separator(label="Chatbox")
        with dpg.child_window(tag="chatWindow", width=580, height=200):
            dpg.add_text("Chat Log:", tag="chatLog", wrap=560)
    
    # Input area
        with dpg.group(horizontal=True):
            dpg.add_input_text(tag="chatInput", width=400, hint="Type your message here...")
            dpg.add_button(label="Send", callback=lambda: _send_message())


"""     with dpg.theme() as global_theme:
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3, category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.myStyleVar_FramePadding, (8,6), category=dpg.mvThemeCat_Core)

    dpg.bind_theme(global_theme) """


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
    
    with open("agent/visualisation/finalOutput.txt", 'r') as file:
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
            dpg.set_value("chatLog", "Strategy generated. Ask questions about it!")

        
        running = False
        _change_ui_state(running)

def _send_message():
    '''Handles sending user input to agent chat system'''
    user_msg = dpg.get_value("chatInput").strip()
    if not user_msg:
        return
    
    # Clear input immediately
    dpg.set_value("chatInput", "")

    # Display user message
    current_log = dpg.get_value("chatLog")
    dpg.set_value("chatLog", f"{current_log}\n\nYou: {user_msg}\n\nAgent: Thinking...")
    
    # Calling Geoff's chat function in background
    threading.Thread(target=_process_chat_message, args=(user_msg,), daemon=True).start()
    

def _process_chat_message(user_question):
    '''Calls Geoff's discuss_strategy function'''
    try:
        # Import it inside this thread function (so it's available when running)
        from agent.decision_logic.run_agent.chat_discuss import discuss_strategy

        # Finds the most recent JSON file in game_state directory
        game_state_dir = Path("agent/decision_logic/run_agent/game_state")
        json_files = list(game_state_dir.glob("*.json"))
        
        if not json_files:
            raise FileNotFoundError("No game state JSON found. Generate a strategy first.")
        
        # Uses most recent file
        latest_json = max(json_files, key=lambda p: p.stat().st_mtime)
        json_filename = latest_json.name
        
        # Calling Geoff's working chat function
        answer = discuss_strategy(json_filename, user_question)
        
        # Update display with response
        current_log = dpg.get_value("chatLog")
        updated = current_log.replace("Agent: Thinking...", f"Agent: {answer}")
        dpg.set_value("chatLog", updated)
        
    except Exception as e:
        current_log = dpg.get_value("chatLog")
        updated = current_log.replace("Agent: Thinking...", f"Agent: Error - {str(e)}")
        dpg.set_value("chatLog", updated)

def _refresh_chat_display():
    '''Reads entire conversation from file and updates display'''
    try:
        with open("agent/visualisation/finalOutput.txt", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse and format for display
        if 'Model/User Strategy Discussion:' in content:
            qa_start = content.find('Model/User Strategy Discussion:')
            conversation = content[qa_start:].strip()
            
            # Format for chat display
            formatted = conversation.replace('Model/User Strategy Discussion:', 'Chat History:')
            formatted = formatted.replace('[User]', '\n\nYou:')
            formatted = formatted.replace('Q:', '\n\nYou:')
            formatted = formatted.replace('A:', '\n\nAgent:')
            
            dpg.set_value("chatLog", formatted)
        else:
            dpg.set_value("chatLog", "No conversation yet. Ask a question about the strategy.")
            
    except Exception as e:
        dpg.set_value("chatLog", f"Error loading chat: {e}")

def _run_agent():
    '''This is the function that runs the ORC and Agent, in that order.
        This will be called as a seperate process.

        Contains timer to serve as an example for now.'''
    time.sleep(8)