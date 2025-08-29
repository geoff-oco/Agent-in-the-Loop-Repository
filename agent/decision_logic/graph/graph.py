from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field      # BaseModel is the state object for our graph as it evolves in play.
from langgraph.graph import StateGraph, END  # Stategraph will allow us nodes and edges and END is the required last node.
from helpers.Helpers import Helpers # import our helper clas for helper functions

# State Object
class ChatState(BaseModel): #Base model arguments our our model and API base at minimum
    # tracks everything about the chat, its used to pass info between nodes in the graph.
    model: str #the model name
    base_url: str # the ollama api
    system: str = "You are an RTS strategy chatbot. Be concise and actionable." # the LLM system prompt
    image_path: Optional[str] = None # this is the path to an image file to attach to the next user message
    messages: List[Dict[str, Any]] = Field(default_factory=list)  # conversation history in a list of dictionaries
    last_reply: Optional[str] = None # the last reply from the LLM, for convenience


# Nodes - these will make up the different points for our agent to perform actions, like a flow graph
def node_chat(state: ChatState) -> ChatState: #This changes the chatstate

    #Our chatbot node, it will add a screenshot to the next message if one was attached, send all messages to Ollama, and save the reply.

    if state.messages and state.messages[-1].get("role") == "user": #Checks the last message is from the user and that there is at least one message.
        last = state.messages[-1]   # Grab the most recent user message

        #if Ollama gave us a list of content pieces instead of a string we process it into a single string
        if isinstance(last.get("content"), list):
            texts = []
            for part in last["content"]:   # Go through each piece of the list
                if isinstance(part, dict) and part.get("type") == "text":
                    # Collect only the text parts
                    texts.append(part.get("text", ""))
            # Join it all up into one big old string of text
            last["content"] = "\n".join(texts) if texts else ""

        # if the user gives an image we covert to base64 for Ollama and only attach to next message
        if state.image_path:
            try:
                last["images"] = [Helpers._file_to_b64(state.image_path)]
            except Exception as e:

                #If the image can't be read simply clear it and return an error, graceful no?
                last["images"] = []
                last["content"] = (last.get("content") or "") + f"\n(Note: image load failed: {e})"

    # Now send all messages to Ollama
    try:
        reply = Helpers._ollama_chat(state.base_url, state.model, state.system, state.messages) #calling our helper method with payload and parmters already set up
    except Exception as e:
        # If Ollama isn’t running or something breaks, give a safe fallback reply.
        reply = (
            "(model unavailable) Minimal fallback: focus economy, spend resources, Game Over man, game over! "
            f"Error: {e}"
        )

    # Add Ollama’s reply into the chat history as an assistant message
    state.messages.append({"role": "assistant", "content": reply})

    # Also store the reply separately in last_reply for history purposes
    state.last_reply = reply

    # Return the updated state so the graph knows what happened and can update accordingly
    return state


# Conditional Edges - As the logic for the agent evolves we will ut our conditional edges in here.


# Graph - this is where the nodes and edges and the path is laid out
def build_graph():

    #The graph = chatstate -> chat -> END
    g = StateGraph(ChatState)       # This initialises a graph using chatState
    g.add_node("chat", node_chat)   # We add the node chat.
    g.set_entry_point("chat")       # we set the entry point to our defined chat node.
    g.add_edge("chat", END)         # we define the endpoint, runs every time the gaph runs its code.
    return g.compile()              # compile the graph

