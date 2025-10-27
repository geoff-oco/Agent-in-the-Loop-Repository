import json
from helpers.helpers import Helpers
from helpers.readers import Readers
from helpers.advise_support import AdviseSupport
from graph.state import ChatState
from validators.validate_phase_slice import validate_phase_slice
from validators.apply_math import apply_math
from validators.compute_certain import compute_certain


def node(state: ChatState) -> ChatState:

    # Run whole phase off of p
    p = int(state.current_phase)

    # Fixes error when summary built first, we need to build runtime from raw game state
    if p == 1 and (not state.runtime or "phases" not in state.runtime):
        state.game_state_raw = Readers.read_json(state.game_state_path)
        pre_summary = None
        pre_rationale = None

        # Preserves the existing summary and rationale
        if state.runtime and isinstance(state.runtime, dict):
            pre_summary = state.runtime.get("summary")
            pre_rationale = state.runtime.get("rationale")

        runtime_built = AdviseSupport.build_runtime(state.game_state_raw)

        # Append the summary after they are chopped, could not figure out the error otherwise
        if pre_summary is not None:
            runtime_built["summary"] = pre_summary
        if pre_rationale is not None:
            runtime_built["rationale"] = pre_rationale

        # Assign to our state
        state.runtime = runtime_built

    # Double check we've got a strategy by this point
    if state.selected_texts is None:
        state.selected_texts = {}

    # pdata is the original phase data
    pdata = state.runtime["phases"][p]

    # Grab our internal prompts and the summary to feed back in each phase
    system_txt = Readers.read_prompt(state.prompts_dir, "system.md") or ""
    advise_txt = Readers.read_prompt(state.prompts_dir, "advise_instructions.md") or ""
    summary_text = (state.runtime or {}).get("summary", "") or ""

    prompt = AdviseSupport.build_phase_prompt(
        p=p,
        pdata=pdata,
        strategy_texts=state.selected_texts,
        summary_text=summary_text,
        system_txt=system_txt,
        advise_txt=advise_txt,
    )

    # Call the LLM, requesting JSON output
    llm = Helpers.get_langchain_llm(state.model, temperature=0.2, max_tokens=900)
    print(f"Sending request for phase {p}...")
    ai = llm.invoke(prompt)

    # Grab the raw text from AI and parse it
    raw = getattr(ai, "output_text", None) or getattr(ai, "content", None) or str(ai)

    # Extract the json response
    try:
        got = Readers.extract_json(raw)
    except Exception:
        got = None
    if not got:
        try:
            got = json.loads(raw)
        except Exception:
            got = {}

    # decs shows model decisions, inserts shows new units added, vflags shows the model decisions that were flagged as invalid
    # Validate phase will run the response through validation and do various fixes and conversions
    decs, inserts, vflags = validate_phase_slice(pdata, got or {})

    # end_snapshot shows the end state of the phase after applying the decisions and inserts, 
    # eff shows the effective transfers, 
    # mflags shows any flags raised during math application
    # Apply math is then used to apply our effective decisions all to get that end snapshot
    eff, end_snapshot, mflags = apply_math(pdata, decs, inserts, meta=(state.runtime.get("meta") or {}))

    # Update our phase and grab flags and end state
    pdata["decisions"] = decs
    pdata["inserts"] = inserts
    pdata["effective_transfers"] = eff
    pdata["end"] = Helpers.dcopy(end_snapshot)
    pdata["flags"] = list(vflags) + list(mflags)

    # We open up the next phase in the raw data and rewrite its start with our own end
    # certain is what we know for sure, possible is what could be true,
    # audit is a full breakdown of how we got there, 
    # This will ensure valid moves from phase to phase are not overwritten
    if (p + 1) in state.runtime["phases"]:
        certain, possible, audit = compute_certain(
            state.runtime,
            state.game_state_raw,
            p,
            decs,
            eff,
            prev_end_snapshot=end_snapshot,
        )

        # Update our runtime state for our final output later
        state.runtime["phases"][p + 1]["start"] = Helpers.dcopy(certain)
        state.runtime["phases"][p + 1]["certain_start"] = Helpers.dcopy(certain)
        state.runtime["phases"][p + 1]["possible"] = possible

    # Now we update our states, current phase will set off our loop again until we hit 4
    state.current_phase = p + 1
    state.last_structured = {
        "phase": p,
        "decisions": decs,
        "inserts": inserts,
        "effective": eff,
        "end": pdata["end"],
        "flags": pdata["flags"],
    }
    state.last_reply = ""
    print(f"completed phase {p}!")
    return state
