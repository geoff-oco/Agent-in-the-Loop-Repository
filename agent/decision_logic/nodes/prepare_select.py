import json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage # ToolMessage used in prepare_select node to capture tool responses, AIMessage, HumanMessage, SystemMessage used for LLM interaction
from helpers.helpers import Helpers
from helpers.readers import Readers
from nodes.tools import load_markdowns #we make our tool call within this node

def node(state):
    # Initialize state variables we can using our helpers and readers
    Helpers.set_strategy_dir(state.strategies_dir) # Set the strategy directory in helpers for use in tool
    names = Readers.list_markdowns(state.strategies_dir) # List all markdown strategy filenames in the strategies directory to be passed to LLM
    Helpers.set_allowed_names(names) # Set the allowed names in helpers for validation in tool
    state.strategy_names = names # Store the strategy names in state for use in prompt to LLM
    #INSERTION POINT
    state.game_state = Readers.read_json_file(state.game_state_path) # Load the game state from the specified JSON file into state.

    llm = Helpers.get_langchain_llm(state.base_url, state.model).bind_tools([load_markdowns], tool_choice="required") # Get the LLM instance and bind the load_markdowns tool, making it a required tool call

    #concatenate our various markdown prompts for our message
    sys_txt = Readers.read_prompt(state.prompts_dir, "system.md")
    glob_txt = Readers.read_prompt(state.prompts_dir, "global_context.md")
    sel_txt = Readers.read_prompt(state.prompts_dir, "select_markdowns.md")
    inst = Readers.read_prompt(state.prompts_dir, "ReadingJSON.md")
    listing = "\n".join(f"- {n}" for n in state.strategy_names)
    game_json = json.dumps(state.game_state, ensure_ascii=False) # Convert game state to JSON string for LLM

    msgs = [] 
    if sys_txt:
        msgs.append(SystemMessage(content=sys_txt))
    msgs.append(HumanMessage(content="\n\n".join([t for t in [glob_txt, sel_txt, inst, listing, game_json] if t])))

    Helpers.log(f"[select] Invoking LLM for first pass with model {state.model} at {state.base_url} with initial tool call...")

    ai: AIMessage = llm.invoke(msgs) # Invoke the LLM with the constructed messages, expecting a tool call in response
    msgs.append(ai) # Append the LLM's response to the message list


    tool_msgs = [] # List to hold any ToolMessage responses from tool calls
    if getattr(ai, "tool_calls", None): # Check if there are any tool calls in the LLM response
        for tc in ai.tool_calls:
            if tc.get("name") != "load_markdowns": # We only handle the load_markdowns tool call here, ignore others
                continue
            args = tc.get("args", {}) or {} # Get the arguments for the tool call, defaulting to empty dict if none

            #multiple attempts to get filename from args, defaulting to a known strategy if none provided
            filename = args.get("filename") or args.get("name") or []
            Helpers.log(f"[select] Tool call to load_markdowns with filename: {filename} 1st try")
            if isinstance(filename, list):
                filename = filename[0] if filename else None
                Helpers.log(f"[select] Tool call to load_markdowns with filename: {filename} 2nd try found in list")
            if not filename:
                filename = "Heavy_Anchor_Light_Flanks.md" 
                Helpers.log(f"[select] No filename provided in tool call, defaulting to {filename}")
            res = load_markdowns.invoke({"filename": filename})

            # Log the tool response
            tool_msgs.append(ToolMessage(content=res, name="load_markdowns", tool_call_id=tc.get("id", "")))

    if not tool_msgs:
        state.errors.append("no_tool_call")
        state.messages = msgs
        return state

    msgs.extend(tool_msgs) # Append any further tool messages to the message list
    data = Readers.extract_json(tool_msgs[-1].content) or {} # Extract JSON data from the last tool message content
    state.selected_names = list(data.get("selected_names", [])) # Store selected strategy names in state
    state.selected_texts = dict(data.get("selected_texts", {})) # Store selected strategy texts in state
    state.messages = msgs # Update state messages with the full conversation history
    return state
