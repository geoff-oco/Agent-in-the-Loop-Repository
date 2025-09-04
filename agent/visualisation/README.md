# User Interface

This module contains the interface the user will control the program with.

## The Buttons

The Ui contains 3 buttons that controls the program

### Generate Strategy
This button activates the agent module (or will in the future), reading the input taken from the screen reading.
This button is disabled at the start until one screen read has been completed.
While a strategy is being generated, the button and the Screen read button are dissabled and the stop button enabled.

### Screen Capture
This button activates the orc module (or will in the future).
While this orc module is running, this button and the Generate Strategy button are dissabled, and the stop button enabled.

### Stop Agent
This sets a flag that stops either the agent or the orc module.
The functionality of this feature may become complicated to implement during implementation.

## The Functions

### run_agent()
This one is responsable for running the agent AND showing the agents output

First, it effects the UI, dissabling and enabling the relevant buttons.
Then it starts the agent (currently has a a timer to represent a big calculation (with early cancel funcitonality)).
After the agent finishes, it reads a text file which will contain the output, and prints it to the screen
Finaly, it resets the UI back to its original state, and the flags.

### run_orc()
This one is responsable for running the ORC module.

Its like the run_agent() function, in that it has starting and ending UI changes.
Inbetween it runs the orc module (Currently timer with cancel)
This function sets the screenCaptured Flag to True. (Which does nothing but may be used to prevent errors in the future)

### _callback functions

These functions are directly tied to the buttons. 
generation_callback() and screenCapture_callback() call the above functions as threads, to allow interactivity with the GUI to continue while these run in the background. This is what makes canceling possible.

stopButton_callback() simply sets the canceling flag to True.