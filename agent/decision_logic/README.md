# Decision Logic Module

This module handles AI reasoning and planning for the agent.



---



\# Agent in the Loop v0.1



This early iteration is a simple command-line agent built with LangGraph that connects to Ollama for local LLM inference.  

It allows interactive chat with an AI model, with optional image input, tailored for real-time tactical feedback. It is designed light that it may be expanded on in the context of aligning the agent with our goals.



The code is heavily commented as a way of assisting fast learning in the early stages of development. It is suggested much of this commenting be removed for the final roduct.



---



\## 1. Installing Ollama



1\. Download and install Ollama from https://ollama.com/

2\. After installation, ensure Ollama is running:

&nbsp;  - Open a browser and go to http://localhost:11434

&nbsp;  - You should see a confirmation message that Ollama is active.

3\. Open shell and pull the required model (Qwen): ollama pull qwen2.5vl:3b



---



\## 2. Running the Program



\### Step 1: Clone \& Navigate  

cd path/to/project



\### Step 2: Install Dependencies  

pip install -r requirements.txt



\### Step 3: Create a Python Virtual Environment  



python -m venv venv



source venv/bin/activate   # On macOS/Linux

venv\\Scripts\\activate      # On Windows



\### Step 4: Run the Program  

python main.py



---



\## 3. Interaction Guide



\- The program starts with a prompt:



&nbsp; Welcome to SkyNet, your Agent in the Loop (type /image <path> to attach an image; /quit to exit)



\- Sending messages: Type directly into the terminal and press Enter.  

\- Quitting: Use `/quit`, `quit`, `exit`, or `:q`.  

\- Attaching an image:  

&nbsp; - Type `/image path/to/your/image.png`  

&nbsp; - On the next message you send, the image will be included with your text.  

&nbsp; - If the image fails to load, an error message is shown, but the conversation continues.  



---



\## 4. Configuration



The program uses a `.env` file for configuration (it is recommended this is added to .gitignore for the final product):  



MODEL\_NAME=qwen2.5vl:3b

OLLAMA\_BASE\_URL=http://localhost:11434



You can edit these values to change the model or Ollama base URL.

