import os # Gives us tools to work with environment variables and file paths
from dotenv import load_dotenv # Lets us load values from a .env file into environment variables
from .graph.graph import build_graph, ChatState  # Import our ChatState class and build_graph function from graph.py

def main():
    load_dotenv()
    
    # Load values from our .env with fallbacks at dev stage
    model = os.getenv("MODEL_NAME", "qwen2.5vl:3b")
    base  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    #Welcome
    print("Welcome to SkyNet, your Agent in the Loop (type /image <path> to attach an image; /quit to exit)\n")

    # Our initial state object, which will track everything about the chat
    state = ChatState(model=model, base_url=base)

    # This will build the graph we defined
    graph = build_graph()

    # Standard conversation loop
    while True:
        user = input("You: ").strip()   # Read user input from terminal
        if not user:                    # If user just presses Enter, skip this turn
            continue

        # Special commands like quit or image
        low = user.lower()
        if low in ("/quit", "quit", "exit", ":q"):   # Check for exit commands
            break
        if low.startswith("/image "):   # Attach an image path for the next user messags, see node_chat in graph.py
            path = user.split(" ", 1)[1].strip().strip('"')  # Extract the image path
            state.image_path = path or None  # Save the path in the state image_path
            print(f"(attached image: {state.image_path})") # Confirm to user
            continue  # Dont send a message this turn image will be sent next turn

        # Add the users text input as a new message in chat history
        state.messages.append({"role": "user", "content": user})

        result = graph.invoke(state.model_dump())  # This runs the graph with current state, and returns a dict
        state = ChatState(**result)                # This converts the returned dict back into a chat state object, then we go again.

        # Print reply from the LLM.
        print(f"\nAssistant:\n{state.last_reply}\n")


if __name__ == "__main__":
    main()
