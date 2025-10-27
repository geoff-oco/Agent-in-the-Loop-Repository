from typing import Any, Dict, List, Tuple


# Function to check and sanitise the model output for a phase slice, mainly decisions on original actions and any inserts
def validate_phase_slice(
    pdata: Dict[str, Any], model_out: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:

    # Our flags are used to determine valid moves and any issues found
    flags: List[str] = []

    # Then we validate decisions by giving defaults and checking for invalid values
    allowed = {"leave", "lock", "delete"}

    # We get our original ids to ensure we have a decision for each
    orig_ids = sorted(pdata.get("orig_actions", {}).keys())

    # md is another decision map, we build it from model output first
    md: Dict[int, Dict[str, Any]] = {}
    for d in model_out.get("decisions") or []:  # Check what we got for decisions from the model
        try:
            mid = int(d.get("id"))
            val = str(d.get("decision", "leave")).lower()  # If no decision, default to leave
            if val not in allowed:
                flags.append(f"invalid_decision:{mid}:{val}")  # Flag invalid decisions and reset to leave
                val = "leave"  # default to leave if invalid

            # We build our map of decisions by id
            md[mid] = {"id": mid, "decision": val}
        except Exception:
            continue
    decisions: List[Dict[str, Any]] = []

    # Ensure we have a decision for each original action, defaulting to leave if missing
    for i in orig_ids:
        decisions.append(md.get(i, {"id": i, "decision": "leave"}))
    if not model_out.get("decisions"):
        flags.append("model:missing_decisions")

    # We now validate inserts, ensuring no duplicates, no zero moves (a move with no units), and enforcing the cap
    # The cap is determined by 5 minus the number of leave + lock decisions, minimum
    num_leave_lock = sum(1 for d in decisions if d["decision"] in ("leave", "lock"))
    num_delete = sum(1 for d in decisions if d["decision"] == "delete")
    cap = max(0, 5 - num_leave_lock)

    # We enforce the cap on inserts
    seen = set()
    inserts: List[Dict[str, Any]] = []  # This will be our valid inserts
    raw_inserts = model_out.get("inserts") or []

    # Checking what we got for inserts from the model
    for ins in raw_inserts:
        try:
            f = str(ins.get("from")).lower()
            t = str(ins.get("to")).lower()

            # from and to must be non-empty and not the same
            L = max(0, int(ins.get("L", 0)))
            H = max(0, int(ins.get("H", 0)))
            R = max(0, int(ins.get("R", 0)))
            if (L + H + R) <= 0:
                continue

            # No duplicates, we use a set of tuples to track seen inserts
            # A duplicate is defined as same from, to and unit counts
            key = (f, t, L, H, R)
            if key in seen:
                continue
            seen.add(key)

            # If passes validation we add it to our inserts
            inserts.append(
                {
                    "from": f,
                    "to": t,
                    "L": L,
                    "H": H,
                    "R": R,
                    "locked": bool(ins.get("locked", False)),
                    "kind": "insert",
                }
            )
        except Exception:
            continue

    # Enforce the cap on inserts, trimming excess and flagging
    if len(inserts) > cap:
        inserts = inserts[:cap]
        flags.append(f"validator:cap_inserts_to_{cap}")

    # These want to make sure we are using our full capacity and not leaving anything on the table
    if num_leave_lock <= 2 and len(inserts) == 0 and cap > 0:
        flags.append("validator:should_insert_but_none")
    if num_delete > 0 and len(inserts) < cap:
        flags.append("validator:consider_reallocating_deleted_units")

    # Our return contains the decisions, inserts and any flags raised during validation
    return decisions, inserts, flags
