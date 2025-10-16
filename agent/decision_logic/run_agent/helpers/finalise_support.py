import json
from typing import Any, Dict, List


# Class to help with finalising our output
class FinaliseSupport:
    # Toggle the visibility of some of our validator info
    SHOW_PHASE_STATE_BLOCKS = False

    # Internal method to format our counts
    @staticmethod
    def _fmt_counts(c: Dict[str, int]) -> str:
        return f'{c.get("L",0)}/{c.get("H",0)}/{c.get("R",0)}'

    # Internal method to format one side of our state
    @staticmethod
    def _fmt_side(s: Dict[str, Any]) -> str:
        return (
            f'Blue {FinaliseSupport._fmt_counts(s.get("blue",{}))} | Red {FinaliseSupport._fmt_counts(s.get("red",{}))}'
        )

    # Internal method to format a transfer line
    @staticmethod
    def _fmt_transfer(t: Dict[str, Any]) -> str:

        # check we have a transfer and get the verb
        verb = "lock" if t.get("locked") else t.get("kind", "")
        return f'{verb} {t.get("from")}->{t.get("to")} ' f'{t.get("L",0)}/{t.get("H",0)}/{t.get("R",0)}'

    # Method to format an action line with decision from model
    @staticmethod
    def _fmt_action_line(action: Dict[str, Any], decision: str) -> str:

        fr, to = action.get("from", "?"), action.get("to", "?")  # From and to
        L, H, R = action.get("L", 0), action.get("H", 0), action.get("R", 0)  # units
        return f"{fr}->{to} {L}/{H}/{R} [{decision}]"

    # This method extracts deleted action IDs from flags
    @staticmethod
    def _deleted_ids_from_flags(flags: List[Any]) -> List[int]:
        # Extract deleted action IDs from flags
        out: List[int] = []
        for f in flags or []:
            if isinstance(f, str) and f.startswith("deleted_action:"):
                try:
                    out.append(int(f.split(":")[1]))  # and append if deleted
                except Exception:
                    pass
        return out

    # For the detail path this will render our full output
    @staticmethod
    def format(runtime: Dict[str, Any], *, include_meta: bool = True) -> str:

        if not runtime:
            return ""
        # Begin our lines
        lines: List[str] = []

        # Render our summary
        summary = runtime.get("summary")
        if isinstance(summary, str) and summary.strip():
            lines.append("Summary")
            lines.append(summary.strip())
            lines.append("")

        # Render our LER saved in meta including favour
        meta = runtime.get("meta", {})
        if include_meta and meta:
            ler = meta.get("ler", {})
            blue = ler.get("blue")
            red = ler.get("red")
            fav = ler.get("favour")
            if blue is not None and red is not None:
                ler_str = f"{blue:.2f}:{red:.2f}" if red != 0 else f"{blue:.2f}:0"
                lines.append("Current LER")
                lines.append(f"{ler_str} in favour of {fav}")
                lines.append("")

        # Our per phase rendering loop
        phases = runtime.get("phases", {})
        for p in sorted(phases.keys()):  # sorted to ensure order
            ph = phases[p]
            lines.append(f"Phase {p}")

            # CERTAIN start from validation hidden with earlier flag, certain start represents the state at the start of the phase unmutated
            st = ph.get("start", {})
            if FinaliseSupport.SHOW_PHASE_STATE_BLOCKS:
                lines.append("Start (CERTAIN)")
                lines.append(f'Blue: {FinaliseSupport._fmt_side(st.get("blue",{}))}')
                lines.append(f'Red1: {FinaliseSupport._fmt_side(st.get("red1",{}))}')
                lines.append(f'Red2: {FinaliseSupport._fmt_side(st.get("red2",{}))}')
                lines.append(f'Red3: {FinaliseSupport._fmt_side(st.get("red3",{}))}')

            # We now render our effective transfers, original actions and deleted actions
            eff: List[Dict[str, Any]] = ph.get("effective_transfers", []) or []  # eff is effective transfers
            orig = ph.get("orig_actions", {}) or {}
            by_id = {a.get("id"): a for a in (orig.values() if isinstance(orig, dict) else [])}

            # Check original actions for locks and leaves and append as appropriate
            actions_block: List[str] = []
            for e in eff:
                kind = (e.get("kind") or "").lower()
                if kind in ("leave", "lock"):
                    actions_block.append(FinaliseSupport._fmt_transfer(e))  # only append if good

            # Check flags for deletions and append those too
            del_ids = FinaliseSupport._deleted_ids_from_flags(ph.get("flags", []))
            for did in del_ids:
                a = by_id.get(did)
                if a:
                    # Use the same line style, but prefix with 'delete' and show the original quantities.
                    actions_block.append(f'delete {FinaliseSupport._fmt_action_line(a, "delete")} (#{did})')

            # Places an em dash if no actions in phase
            lines.append("Actions")
            if actions_block:
                lines.extend(actions_block)
            else:
                lines.append("—")

            # Valid iinserts from effective transfers
            inserts_block: List[str] = []
            for e in eff:
                if (e.get("kind") or "").lower() == "insert":
                    inserts_block.append(FinaliseSupport._fmt_transfer(e))

            # Give an em dash if no inserts
            lines.append("Inserts")
            if inserts_block:
                lines.extend(inserts_block)
            else:
                lines.append("—")

            # End CERTAIN validation values, hidden with flag, but used in validations
            e = ph.get("end", {})
            if FinaliseSupport.SHOW_PHASE_STATE_BLOCKS:
                lines.append("End (CERTAIN)")
                lines.append(f'Blue: {FinaliseSupport._fmt_side(e.get("blue",{}))}')
                lines.append(f'Red1: {FinaliseSupport._fmt_side(e.get("red1",{}))}')
                lines.append(f'Red2: {FinaliseSupport._fmt_side(e.get("red2",{}))}')
                lines.append(f'Red3: {FinaliseSupport._fmt_side(e.get("red3",{}))}')
                lines.append("")
            else:
                lines.append("")

        # Finally we render our rationale
        rationale = runtime.get("rationale")
        if isinstance(rationale, str) and rationale.strip():
            lines.append("Rationale")
            lines.append(rationale.strip())
            lines.append("")

            # Clean it all up and join it allll together
        return "\n".join(lines).strip()

    # ---------- simple finalise support ----------

    # Simpler formatting for a single LLM return
    @staticmethod
    def format_simple(simple: Dict[str, Any]) -> str:
        # check it is our simple return and give our title
        if not isinstance(simple, dict):
            return "Simple Advice\n\n(no data)"
        # Begin lines
        lines: List[str] = ["Simple Advice", ""]

        # Grab summary and add to lines
        summ = str(simple.get("summary", "") or "").strip()
        if summ:
            lines += ["Summary", summ, ""]

        # Grab LER and favour and add to lines
        meta = simple.get("meta", {})
        fav = meta.get("ler_favour")
        ler = meta.get("ler", {})
        blue = ler.get("blue")
        red = ler.get("red")
        if fav and blue is not None and red is not None:
            ler_str = f"{blue:.2f}:{red:.2f}" if red != 0 else f"{blue:.2f}:0"
            lines += [f"LER: {ler_str} in favour of: {fav}", ""]

        # Grab phases
        phases = simple.get("phases") or []
        if not phases:
            raw = json.dumps(simple, ensure_ascii=False, indent=2)
            lines += ["(no phases in output)", "", raw]
            return "\n".join(lines).strip()

        # For eachphase grab the bases and the advice piece for each move as well as a summary
        for ph in phases:
            lines.append(f"Phase {ph.get('phase')}")
            for b in ph.get("bases") or []:
                nm = (b.get("name") or "").capitalize() or "Red?"
                lines.append(nm)
                lines.append(f"- Summary: {b.get('summary','')}")
                lines.append(f"- Lock: {b.get('lock','')}")
                lines.append(f"- Delete: {b.get('delete','')}")
                lines.append(f"- Insert: {b.get('insert','')}")
                lines.append("")

        # Grab the rationale and append
        rat = str(simple.get("rationale", "") or "").strip()
        if rat:
            lines += ["Rationale", rat, ""]

        # Sometimes gives optional notes?? I've written this to grab those.
        if simple.get("notes"):
            lines += ["Notes", str(simple.get("notes")), ""]

        # Clean and return it all
        return "\n".join(lines).strip()
