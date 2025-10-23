from __future__ import annotations
import json
from pathlib import Path
from typing import Dict
from graph.state import ChatState
from helpers.helpers import Helpers
from helpers.readers import Readers
from langchain_core.messages import SystemMessage, HumanMessage
from nodes.tools import load_markdowns

# Set for this node only, will grab a snippet of strategies
PREVIEW_CHARS = 600


# Our node for strategy selection and path determination
def node(state: ChatState) -> ChatState:

    # Grab all markdown titles
    Helpers.list_markdowns(state.strategies_dir)
    # List these in a ready package for tool calls
    names = Helpers.get_allowed_names()

    if not names:
        return state

    # Define model
    llm = Helpers.get_langchain_llm(state.model, temperature=0.0, max_tokens=400)

    # Bind our tool
    llm = llm.bind_tools([load_markdowns], tool_choice="load_markdowns", strict=True)

    # Grab our prompts for tool call
    sys_txt = Readers.read_prompt(state.prompts_dir, "system.md") or ""
    sel_txt = Readers.read_prompt(state.prompts_dir, "select_markdowns.md") or ""

    # Gives the LLM a snippet from each strategy so it knows what it is choosing
    previews: Dict[str, str] = {}
    for n in names:
        p = Path(state.strategies_dir) / n
        try:
            previews[n] = p.read_text(encoding="utf-8")[:PREVIEW_CHARS]
        except Exception:
            previews[n] = ""

    # Compact game context for the model to analyse
    selection_context = Readers.build_selection_context(state)

    # Our actual message
    user_payload = {
        "task": (
            "Analyse the current game_state and pick exactly one strategy filename "
            "from 'filenames' that best fits the situation. "
            "Return STRICT JSON ONLY matching the output_schema."
        ),
        "filenames": names,
        "previews": previews,
        "game_state": selection_context,
        "output_schema": {"selected": "string  # must equal one of 'filenames'"},
    }

    msgs = [
        SystemMessage(content=sys_txt.strip()),
        SystemMessage(content=sel_txt.strip()),
        HumanMessage(content=json.dumps(user_payload, ensure_ascii=False)),
    ]
    print("Requesting strategy selection...")
    ai = llm.invoke(msgs)

    # Grab the raw text from AI and parse it, expecting JSON
    tool_calls = getattr(ai, "tool_calls", None) or []

    # We want a tool call, if none we fallback to first strategy
    if not tool_calls:
        if names:
            pick = names[0]
            out_json = load_markdowns.invoke({"filename": pick})  # Invoke our tool manually, sans LLM
            loaded = json.loads(out_json)
        else:
            loaded = {"selected_names": [], "selected_texts": {}}
    else:
        loaded = None

        # Check the tool calls for our load_markdowns call
        for tc in tool_calls:

            # Ensure it's the right tool
            if (tc.get("name") or "").lower() == "load_markdowns":
                args = tc.get("args") or {}
                filename = args.get("filename")  # Grab the filename

                # Default to first if missing or empty
                if not filename:
                    print("WARNING: Tool args missing; falling back to first strategy.")
                    filename = names[0] if names else None
                if filename:

                    # Tool will give us the json we need
                    out_json = load_markdowns.invoke({"filename": filename})

                    # Parse the JSON response
                    loaded = json.loads(out_json)
                break

        if not loaded:

            # Something went really wrong, fallback to first strategy
            print("WARNING: No valid tool call found; falling back to first strategy.")
            if names:
                out_json = load_markdowns.invoke({"filename": names[0]})  # Invoke our tool manually, sans LLM
                loaded = json.loads(out_json)  # Parse the result
            else:
                loaded = {"selected_names": [], "selected_texts": {}}

    # Load our states from the tool call
    state.selected_names = loaded.get("selected_names", [])
    state.selected_texts = loaded.get("selected_texts", {})

    # Finally we determine the path from simple or detailed
    try:
        mode = Helpers.get_mode_from_gamepath(state.game_state_path)
    except Exception:
        mode = "detail"
    print(f"Path determined for advice: {mode}")
    state.mode = mode

    return state
