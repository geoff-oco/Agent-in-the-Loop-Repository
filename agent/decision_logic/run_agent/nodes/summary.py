from __future__ import annotations
from typing import Any, Dict, List
import json
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from helpers.helpers import Helpers
from helpers.readers import Readers
from graph.state import ChatState


# Our node to create a starting summary of intent
def node(state: ChatState) -> ChatState:

    # Grab our LLM
    llm = Helpers.get_langchain_llm(state.model, temperature=0.2, max_tokens=300)

    # Prepare our prompts
    sys_txt = Readers.read_prompt(state.prompts_dir, "system.md") or ""
    read_json_txt = Readers.read_prompt(state.prompts_dir, "ReadingJSON.md") or ""

    # Check for raw json
    if not state.game_state_raw:
        state.game_state_raw = Readers.read_json(state.game_state_path)
    gs_json = json.dumps(state.game_state_raw or {}, ensure_ascii=False)

    # Prepare the message packets
    msgs: List[Any] = [
        SystemMessage(content=sys_txt),
        SystemMessage(content="You MUST answer in strict JSON. No markdown outside JSON."),
        SystemMessage(content=read_json_txt),
        HumanMessage(
            content=(
                "Write a concise THREE-LINE plan summary (one line per phase) for Blue.\n"
                "Be concrete and goal-focused. No move-by-move detail.\n"
                f"follow the strategy here when coming up with a plan {state.selected_texts}"
                'Return STRICT JSON only:\n{\n  "summary": "Line1\\nLine2\\nLine3"\n}\n\n'
                "Game state follows (read-only):\n"
                f"{gs_json}"
            )
        ),
    ]

    # Send it
    print("Requesting Summary...")
    ai: AIMessage = llm.invoke(msgs)
    raw = getattr(ai, "output_text", None) or getattr(ai, "content", None) or ""

    # Parse JSON to grab summary section
    try:
        data: Dict[str, Any] = Readers.extract_json(raw)
        print("Summary completed!")
    except Exception:
        try:
            data = json.loads(raw or "{}")
        except Exception:
            data = {}
    summary = str((data or {}).get("summary", "")).strip() or raw.strip()

    if state.runtime is None:
        state.runtime = {}

    # Assign our summary to state
    state.runtime["summary"] = summary
    return state
