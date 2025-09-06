#The aim will be to eliminate this when we integrate with OCR and image analysis to get game state directly from screenshots.
#import dotenv to load environment variables from a .env file.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
from graph.graph import build_graph #our graph builder function
from graph.state import ChatState #our state class for the graph

if __name__ == "__main__":
    app = build_graph() #This will build the graph from our nodes and state class
    out = app.invoke(ChatState()) 
    print((out.get("last_reply") if isinstance(out, dict) else getattr(out, "last_reply", None)) or "No advice available.")
