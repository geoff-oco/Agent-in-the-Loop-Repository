from typing import Any, Dict, List, Tuple
from copy import deepcopy
from helpers.phase_math import PhaseMath
from helpers.advise_support import AdviseSupport

# This is where we use our phase math to determine the actual effective moves and resulting end state
def apply_math(
        pdata: Dict[str, Any],
        decisions: List[Dict[str, Any]],
        inserts: List[Dict[str, Any]],
        *,
        meta: Dict[str, Any] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
        
        # we want a deep copy of the start state to avoid mutating input data
        start = deepcopy(pdata["start"])

        #eff will store our effective moves, flags will store any issues we find
        eff: List[Dict[str, Any]] = []
        flags: List[str] = []

        # budgets is the big one, we track original budget for original moves and insert budget for inserts
        # we start with the original blue counts at each location
        orig_budget: Dict[str, Dict[str, int]] = {
            b: deepcopy(start.get(b, {}).get("blue", PhaseMath.vec()))
            for b in start.keys()
        }
        # This is the budget for inserts, starts the same as original budget but is decremented by original moves
        insert_budget: Dict[str, Dict[str, int]] = {
            b: deepcopy(start.get(b, {}).get("blue", PhaseMath.vec()))
            for b in start.keys()
        }

        # map of decisions by action id for easy lookup, default to leave if not found
        dmap = {d["id"]: d.get("decision", "leave") for d in (decisions or [])}

        # we build our effective here, ensuring original moves/budget comes first
        for aid, a in sorted(pdata.get("orig_actions", {}).items()):
            dec = dmap.get(aid, "leave")
            # handle deletions and unexpected decisions by skipping and flagging
            if dec == "delete":
                flags.append(f"deleted_action:{aid}")
                continue
            if dec not in ("leave", "lock"):
                flags.append(f"unexpected_decision:{aid}:{dec}")
            
            # declare from and to as strings for consistency, get vector of move and budget at from location
            f = str(a["from"])
            t = str(a["to"])
            vec = PhaseMath.vec(a["L"], a["H"], a["R"])
            bud = orig_budget.get(f, PhaseMath.vec())

            #take is the actual move we can make, clamped by budget
            take = {
                "L": min(bud.get("L", 0), vec["L"]),
                "H": min(bud.get("H", 0), vec["H"]),
                "R": min(bud.get("R", 0), vec["R"]),
            }
            # if we can't take what we wanted, flag it
            if take != vec:
                flags.append(f"clamped:action:{aid}")
            # if we can't take anything, flag and skip
            if PhaseMath.sum_counts(take) == 0:
                flags.append(f"nullified:action:{aid}")
                continue

            #adjust our budgets accordingly, we reduce original budget by what we take, insert budget is also reduced as original moves reduce what can be inserted
            orig_budget[f] = PhaseMath.sub(bud, take)
            insert_budget[f] = PhaseMath.sub(insert_budget.get(f, PhaseMath.vec()), take)

            # check for lock had a bit of trouble with things defaulting to leve, so explicit check
            is_lock = (dec == "lock")
            eff.append({
                   "kind": "lock" if is_lock else "leave",                   
                   "from": f, "to": t,
                   "L": take["L"], "H": take["H"], "R": take["R"],
                   "locked": True if is_lock else bool(a.get("locked", False)),
                   })


        # Next we will handle the inserts now locked moves are out of the way and deletions have added to budget, similar loop to before
        for ins in (inserts or []):
            f = str(ins["from"])
            t = str(ins["to"])
            vec = PhaseMath.vec(ins["L"], ins["H"], ins["R"])
            bud = insert_budget.get(f, PhaseMath.vec())
            # if no budget at all, flag and skip
            if PhaseMath.sum_counts(bud) == 0:
                flags.append(f"illegal_insert:no_start_blue:{f}")
                continue
            # take is what we can actually insert, clamped by budget
            take = {
                "L": min(bud.get("L", 0), vec["L"]),
                "H": min(bud.get("H", 0), vec["H"]),
                "R": min(bud.get("R", 0), vec["R"]),
            }
            # if we can't take what we wanted, flag it
            if take != vec:
                flags.append(f"clamped:insert:{f}")
            # if we can't take anything, flag and skip
            if PhaseMath.sum_counts(take) == 0:
                flags.append(f"nullified:insert:{f}->{t}")
                continue

            # adjust insert budget only
            insert_budget[f] = PhaseMath.sub(bud, take)
            eff.append({
                "kind": "insert",
                "from": f, "to": t,
                "L": take["L"], "H": take["H"], "R": take["R"],
                "locked": bool(ins.get("locked", False))
            })

        # now we apply our effective moves to the start to get our end snapshot
        end_snapshot = deepcopy(start)
        for tr in eff:
            f = str(tr["from"])
            t = str(tr["to"])
            delta = {"L": tr["L"], "H": tr["H"], "R": tr["R"]} #move vector for this transfer
            # ensure from and to exist in end snapshot and have blue/red sides
            if f not in end_snapshot:
                end_snapshot[f] = {"blue": PhaseMath.vec(), "red": PhaseMath.vec()}
            if t not in end_snapshot:
                end_snapshot[t] = {"blue": PhaseMath.vec(), "red": PhaseMath.vec()}

            # apply the move, subtract from from and add to to
            # we use PhaseMath methods to ensure no negatives creep in
            end_snapshot[f]["blue"] = PhaseMath.sub(end_snapshot[f]["blue"], delta)
            end_snapshot[t]["blue"]  = PhaseMath.add(end_snapshot[t]["blue"], delta)

        # as a safe bet we clamp negatives to zero, shouldn't be needed but just in case
        for bname, sides in end_snapshot.items():
            sides["blue"] = PhaseMath.clamp_nonneg(sides.get("blue", PhaseMath.vec()))
            sides["red"]  = PhaseMath.clamp_nonneg(sides.get("red", PhaseMath.vec()))

        # finally we resolve control, which may have changed due to moves
        end_snapshot = AdviseSupport.resolve_control(end_snapshot, meta or {})

        # return our effective moves, end snapshot and any flags we found
        return eff, end_snapshot, flags
