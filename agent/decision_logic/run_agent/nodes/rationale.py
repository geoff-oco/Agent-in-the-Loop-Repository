from __future__ import annotations
from typing import Any, Dict, List
import json
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from helpers.helpers import Helpers
from helpers.readers import Readers
from graph.state import ChatState


def node(state: ChatState) -> ChatState:

    # Grab our LLM and prompts
    llm = Helpers.get_langchain_llm(state.model, temperature=0.2, max_tokens=400)
    sys_txt = Readers.read_prompt(state.prompts_dir, "system.md") or ""
    summary_text = (state.runtime or {}).get("summary", "") or ""

    # Abridged will be a simplified version of decisions we got from model and how it changed our gamestate
    abridged = {}
    if state.runtime and isinstance(state.runtime.get("phases"), dict):
        try:
            for p, pdata in state.runtime["phases"].items():
                if isinstance(pdata, dict):
                    abridged[str(p)] = {
                        "flags": pdata.get("flags", []),
                        "decisions": pdata.get("decisions", []),
                    }
        except Exception:
            abridged = {}

    # For the rationale we will package our info into a more specified prompt
    content = (
        "Write 3 to 6 concise sentences explaining WHY the chosen plan across the three phases strengthens Blue's position."
        f"We built our startegy off of this original plan:\n\n{state.selected_texts}\n\n"
        f'Use the summary we built with that strategy guide your rationale:\n"""\n{summary_text}\n"""\n'
        " Mention key tradeoffs or risks briefly.\n"
        'Return STRICT JSON only:\n{\n  "rationale": "sentence 1 ..."\n}\n\n'
        f"Artifacts (abridged):\n{json.dumps(abridged, ensure_ascii=False)}"
    )

    # Compose everything for the LLM
    msgs: List[Any] = [
        SystemMessage(content=sys_txt),
        SystemMessage(content="You MUST answer in strict JSON. No extra keys or markdown."),
        HumanMessage(content=content),
    ]

    # Send it
    print("Requesting Rationale...")
    ai: AIMessage = llm.invoke(msgs)

    # Grab the reply
    raw = getattr(ai, "output_text", None) or getattr(ai, "content", None) or ""

    # Parse the json
    try:
        data: Dict[str, Any] = Readers.extract_json(raw)
        print("Rationale completed!")
    except Exception:
        try:
            data = json.loads(raw or "{}")
        except Exception:
            data = {}

    # Extract the rationale portion and clean
    rationale = str((data or {}).get("rationale", "")).strip() or raw.strip()

    if state.runtime is None:
        state.runtime = {}
    # Finally append the rationale to our state
    state.runtime["rationale"] = rationale
    return state
