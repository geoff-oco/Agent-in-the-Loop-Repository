from __future__ import annotations
import json
from typing import Any, Dict, List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from graph.state import ChatState
from helpers.readers import Readers
from helpers.helpers import Helpers
from helpers.advise_support import AdviseSupport


# Our advice node for the simple route
def node(state: ChatState) -> ChatState:
    # Grab gamestate as a whole, and our simple route prompts
    simple_raw: Dict[str, Any] = Readers.read_json(state.game_state_path)
    sys_txt = Readers.read_prompt(state.prompts_dir, "Simple_System.md") or ""
    read_txt = Readers.read_prompt(state.prompts_dir, "Simple_Reading.md") or ""
    advice_tx = Readers.read_prompt(state.prompts_dir, "Simple_Advice.md") or ""

    # Grab our meta information like LER and phases
    phases = simple_raw.get("phases") or []
    favour = ((simple_raw.get("meta") or {}).get("ler") or {}).get("favour", "")
    hints: Dict[str, Any] = {"net": {}, "outcome": {}}

    # Check each phase, compute its net movements and compare to next movement
    for i, ph in enumerate(phases):
        pnum = int(ph.get("phase", i + 1))
        before_p = ph.get("before") or {}
        after_p = ph.get("after") or {}
        hints["net"][str(pnum)] = AdviseSupport.simple_net_movement(before_p, after_p)
        if i + 1 < len(phases):
            before_p1 = phases[i + 1].get("before") or {}

            # We save it all to hints to brute force a little context on the game to the model
            hints["outcome"][str(pnum)] = AdviseSupport.simple_infer_outcome(after_p, before_p1, favour=favour)

    # Build our message parts from all of this
    strategy_texts = state.selected_texts or {}
    payload = {"strategy": strategy_texts, "simple_json": simple_raw, "computed_hints": hints}

    llm = Helpers.get_langchain_llm(state.model, temperature=0.2, max_tokens=2500)

    # Finalise the structure for our model
    msgs: List[Any] = [
        SystemMessage(content=sys_txt),
        SystemMessage(content="Return STRICT JSON only. No markdown outside JSON."),
        SystemMessage(content=read_txt),
        SystemMessage(content=advice_tx),
        HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
    ]

    # Send it
    print("Requesting simple advice...")
    ai: AIMessage = llm.invoke(msgs)
    raw = getattr(ai, "output_text", None) or getattr(ai, "content", None) or ""

    # Parse the json to extract our simple output
    try:
        data: Dict[str, Any] = Readers.extract_json(raw)
    except Exception:
        try:
            data = json.loads(raw or "{}")
        except Exception:
            data = {}

    # Place it into our state to be finalised
    state.simple_output = data if isinstance(data, dict) else {}
    state.last_reply = ""
    return state
