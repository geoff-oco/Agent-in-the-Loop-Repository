import json
from typing import Any, Dict, List
from copy import deepcopy
from helpers.phase_math import PhaseMath

#Helper functions for our advise step, fair bit here
class AdviseSupport:

   # Our detailed version helpers

    # This function builds the runtime structure from the game definition for easier processing
    @staticmethod
    def build_runtime(game: Dict[str, Any]) -> Dict[str, Any]:
        #Start with the LER info and phases
        runtime: Dict[str, Any] = {
            "meta": game.get("meta", {}),
            "phases": {}
        }
        #Grab each phase in turn so we can normalise and store it
        for ph in game.get("phases", []):
            try:
                p = int(ph.get("phase"))
            except Exception:
                continue

            #normalisation process, we want to ensure we have all the bases in lower case and all the counts as integers
            norm_start: Dict[str, Any] = {}
            for base_name, sides in (ph.get("start") or {}).items():
                b = str(base_name).lower()
                blue = dict((sides.get("blue") or {}))
                red  = dict((sides.get("red") or {}))
                #we ensure the counts are integers and default to 0 if not present
                norm_start[b] = {
                    "blue": {"L": int(blue.get("L",0)), "H": int(blue.get("H",0)), "R": int(blue.get("R",0))},
                    "red":  {"L": int(red.get("L",0)),  "H": int(red.get("H",0)),  "R": int(red.get("R",0))},
                }

            # we also normalise the actions into a dictionary keyed by id for easy access
            actions: Dict[int, Dict[str, Any]] = {}
            for a in ph.get("actions", []):
                try:
                    aid = int(a.get("id"))
                except Exception:
                    continue
                # This is the action structure we will use
                actions[aid] = {
                    "id": aid,
                    "from": str(a.get("from")).lower(),
                    "to": str(a.get("to")).lower(),
                    "L": int(a.get("L", 0)),
                    "H": int(a.get("H", 0)),
                    "R": int(a.get("R", 0)),
                    "locked": bool(a.get("locked", False)),
                }

            # We use deepcopy to ensure that each phase's data is independent and not affected by later mutations.
            runtime["phases"][p] = {
                "start": deepcopy(norm_start), 
                "start_orig": deepcopy(norm_start),
                "orig_actions": actions,
                "decisions": [],
                "inserts": [],
                "effective_transfers": [],
                "end": deepcopy(norm_start),
                "flags": [],
                "possible": {},
            }
        return runtime


    # A helper to resolve a single base's control situation
    @staticmethod
    def _resolve_control_one(base_snapshot: Dict[str, Any], favour: str) -> Dict[str, Any]:
        #Grab from the snapshot the two sides
        blue = base_snapshot.get("blue", {"L": 0, "H": 0, "R": 0})
        red  = base_snapshot.get("red",  {"L": 0, "H": 0, "R": 0})
        #Sum all the counts for each side into one force
        bt = PhaseMath.sum_counts(blue)
        rt = PhaseMath.sum_counts(red)
        #If either side is zero we have a clear winner already
        if bt == 0 or rt == 0:
            return base_snapshot
        #If a force is larger they win...simple but seems to be working enough
        if bt > rt:
            winner = "blue"
        elif rt > bt:
            winner = "red"
        
        #If neither side is better we go to the LER or default to red
        else:
            winner = "red" if (favour or "").strip().lower() == "red" else "blue"
        out = deepcopy(base_snapshot)

        #Finally we take for return the winner and remove all units from the loser
        if winner == "blue":
            out["red"] = PhaseMath.vec()
        else:
            out["blue"] = PhaseMath.vec()
        return out

    # This is the main method to resolve all bases in a snapshot for control
    @staticmethod
    def resolve_control(snapshot: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
        # We grab the favour from the meta if present
        try:
            favour = str(((meta or {}).get("ler") or {}).get("favour", "")).strip()
        except Exception:
            favour = ""
        #We deepcopy to avoid mutating the original
        out = deepcopy(snapshot)
        #Run through each base and resolve control for the whole snapshot
        for bname, sides in list(out.items()):
            blue = sides.get("blue", {})
            red  = sides.get("red", {})
            #Annnd then only if both sides are present do we need to resolve
            if PhaseMath.sum_counts(blue) > 0 and PhaseMath.sum_counts(red) > 0:
                out[bname] = AdviseSupport._resolve_control_one(sides, favour)
        return out

    #Since the prompt is difficult and advise was filling up transferred it here to a method
    @staticmethod
    def build_phase_prompt(
    p: int,
    pdata: Dict[str, Any],
    strategy_texts: Dict[str, str],
    summary_text: str,
    system_txt: str,
    advise_txt: str,
) -> str:
        #We take the action ids and sort them for clarity which we need for the output
        ids = sorted(pdata.get("orig_actions", {}).keys())
        ids_str = ", ".join(str(i) for i in ids)

        #Provide an example output structure to the LLM for accuracy
        example = {
            "phase": p,
            "decisions": [
                {"id": 101, "decision": "leave"},
                {"id": 102, "decision": "delete"},
                {"id": 103, "decision": "lock"}
            ],
            "inserts": [
                {"from": "red1", "to": "red2", "L": 1, "H": 0, "R": 0, "locked": False},
                {"from": "red1", "to": "red3", "L": 0, "H": 1, "R": 0, "locked": False},
                {"from": "blue", "to": "red2", "L": 0, "H": 0, "R": 1, "locked": False}
            ]
        }
        example_json = json.dumps(example, indent=2)
        #Join this with our selected strategy
        strategies = "\n\n".join(strategy_texts.values()) if strategy_texts else ""

        #Here we build the read-only snapshot section
        st_lines = []
        st_lines.append("START SNAPSHOT (read-only):")
        for base, sides in pdata.get("start", {}).items():
            #We take both sides and ensure we have defaults for missing values
            b = sides.get("blue", {})
            r = sides.get("red", {})
            st_lines.append(
                f"- {base}: BLUE L/H/R={b.get('L',0)}/{b.get('H',0)}/{b.get('R',0)} | "
                f"RED L/H/R={r.get('L',0)}/{r.get('H',0)}/{r.get('R',0)}"
            )
        st_lines.append("ACTIONS (read-only):")
        # In this loop we print out all the actions in id order for clarity
        for a in pdata.get("orig_actions", {}).values():
            st_lines.append(f"- id {a['id']}: {a['from']} -> {a['to']} L/H/R={a['L']}/{a['H']}/{a['R']}")
        #Added a little info on the actual unit stats
        unit_hints = (
            "Unit hints: Light HP=4 (atk=2), Heavy HP=4 (atk=4), Ranged HP=1 (atk=1); "
            "use as intuition only; do not simulate battles."
        )

        # We build our preface to the phase prompt from the strategy, system prompt, advise instructions and our previously generated summary for what we will do.
        preface_blocks: List[str] = []
        if system_txt.strip():
            preface_blocks.append(system_txt.strip())
        if advise_txt.strip():
            preface_blocks.append(advise_txt.strip())
        if summary_text:
            preface_blocks.append("### SUMMARY (3 lines)\n" + summary_text.strip())
        if strategies:
            preface_blocks.append("### STRATEGY NOTES\n" + strategies)

        preface = "\n\n".join(preface_blocks).strip()

        #Then we order everything into our final prompt to return
        prompt = (
            f"{preface}\n\n"
            f"### UNIT HINTS\n{unit_hints}\n\n"
            "### PHASE INPUT (do not echo)\n"
            + "\n".join(st_lines) +
            "\n\n### OUTPUT FORMAT (illustrative only, ids will differ)\n"
            f"{example_json}\n"
        )
        return prompt

    # ---------- simple advise helpers ----------

    #This will calculate the net movement of blue forces between two snapshots
    @staticmethod
    def simple_net_movement(before: dict, after: dict) -> dict:
        #We grab all bases mentioned in either snapshot
        bases = set((before or {}).keys()) | set((after or {}).keys())
        net = {}
        #For each base we get the blue counts before and after
        for b in bases:
            b0 = deepcopy((before.get(b) or {}).get("blue", {}))
            b1 = deepcopy((after.get(b)  or {}).get("blue", {}))
            #We calculate the non-negutive difference between after and before
            delta = PhaseMath.clamp_nonneg(PhaseMath.sub(b1, b0))
            #annd we store this in the output
            net[b] = {"L": delta.get("L",0), "H": delta.get("H",0), "R": delta.get("R",0)}
        return net

    #This method in detail compares two snapshots and infers the outcome for each base to assist the model
    @staticmethod
    def simple_infer_outcome(after_p: dict, before_p1: dict, favour: str = "") -> dict:
        #We grab all bases mentioned in either snapshot
        bases = set((after_p or {}).keys()) | set((before_p1 or {}).keys())
        out = {}
        #Favour is based on LER preference if present
        fav = (favour or "").lower()
        #For each base we get the blue counts before and after 
        #aB = after blue, nB = next blue, nR = next red, bt = blue total, rt = red total
        for b in bases:
            aB = ((after_p.get(b) or {}).get("blue") or {})
            nB = ((before_p1.get(b) or {}).get("blue") or {})
            nR = ((before_p1.get(b) or {}).get("red")  or {})
            bt, rt = PhaseMath.sum_counts(nB), PhaseMath.sum_counts(nR)
            #If either side is zero we have a clear winner already
            # If either side has more they win...simple but seems to be working enough
            if bt > 0 and rt == 0:
                shift = "blue_control"
            elif rt > 0 and bt == 0:
                shift = "red_control"
            elif bt == 0 and rt == 0:
                shift = "empty"
            #For ties we go to the LER or default to red
            else:
                shift = "tie_red" if fav == "red" else "tie_blue"
            # Return the full values but also the implied outcome of the move
            out[b] = {"blue_after": aB, "blue_next": nB, "red_next": nR, "control_shift": shift}
        return out
