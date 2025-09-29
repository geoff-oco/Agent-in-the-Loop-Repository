# User Interface

The Visulisation file contains the interface the user will control the program with.\

requirements.txt is in the external_overlay folder.

## Modules:
+ **external_overlay:**
> This module is responsable for setting up the dearPyGui engine, and using pyWin32 to allow it to exist as an overlay, and to hook onto the Game.

+ **main**
> Module that calls external_overlay and passes ui as an argument. Program is run from here.
>
> **NOTE:** The game (RTSViewer) must be running before you run this file.

+ **ui**
> ui module handles the user interface layout and functionality

## Output:
**finalOutput.txt** is where the results of the agent will be placed to be read from by the ui.

## UI Functions
### ui
Sets dearPyGui interface layout, ordering buttons, and what functions they call.

### _callback functions
These functions are directly tied to the buttons:

+ **_generation_callback()** calls the _generate_button_pressed function as a thread, to allow interactivity with the GUI to continue. This is what makes canceling possible.

+ **_stopButton_callback()** simply sets the global running flag to false. This will be read by _generate_button_pressed() to let it know to kill the agent process.

### _generate_button_pressed()
When this button is pressed, it opens the txt file it will be reading from. If the
agent has run without being canceled it will print that text onto the output window.
        
The agent will be started in this function, called as another process. If the running flag is set
to false via cancel button press, this process is terminated early.

This function also manages the ui state changes while running

### _run_agent()
This one is responsable for running the agent. Its called as a seperate process

> For intergration, this is where you run your modules from.



