# User Interface

This module contains the interface the user will control the program with.

## main
Module that calls external_overlay and passes ui as an argument. Program is run from here.

NOTE: The game (RTSViewer) must be running before you run this file.

## external_overlay
This module is responsable for setting up the dearPyGui engine, and using pyWin32 to allow it to exist as an overlay, and to hook onto the Game.

## ui_new
ui module handles the user interface layout and functionality. Most of our code is here.

## ui function
Sets dearPyGui layout.

### _callback functions

These functions are directly tied to the buttons. 
_generation_callback() and _screenCapture_callback() call functions as threads, to allow interactivity with the GUI to continue while these run in the background. This is what makes canceling possible.

_stopButton_callback() simply cancels the run_agent() and run_orc functions

### _run_agent()
This one is responsable for running the agent AND showing the agents output

Starts the agent (currently has a a timer to represent a big calculation (with early cancel funcitonality)).
After the agent finishes, it reads a text file which will contain the output, and prints it to the screen
Finaly, it resets the UI back to its original state, and the flags.

### _run_orc()
This one is responsable for running the ORC module.

Its like the run_agent() function, in that it has starting and ending UI changes.
Inbetween it runs the orc module (Currently timer with cancel)

## UserInterface
old ui module, no longer in use