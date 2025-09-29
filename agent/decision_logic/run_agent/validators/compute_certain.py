from typing import Any, Dict, List, Tuple
from copy import deepcopy #fixed issues with copying end to next start
from helpers.phase_math import PhaseMath
from helpers.advise_support import AdviseSupport

# this method ensures that the next phases base numbers, if no deletions will equal their original adjusted by inserts
def compute_certain(
        runtime: Dict[str, Any],
        game_state_raw: Dict[str, Any],
        phase_index: int,
        decisions: List[Dict[str, Any]],
        effective: List[Dict[str, Any]],
        prev_end_snapshot: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        # pahse index taken from our current phase state
        p = phase_index
        # declare for phase +1
        p1 = p + 1
        meta = runtime.get("meta", {})
        # this is our deepcopied original start for phase 1
        start_orig_p1 = deepcopy(runtime["phases"][p1]["start_orig"])
        # this is our deepcopied end from the previous phase
        end_p = deepcopy(prev_end_snapshot) 

        # a map of our original actions and llm decisions
        dmap = {d["id"]: d.get("decision", "leave") for d in (decisions or [])}

        # assign each of these for further use
        actions_p = runtime["phases"][p].get("orig_actions", {}) or {}
        inbound_ids_by_base: Dict[str, List[int]] = {}
        # this loop is to determine inbound actions to each base
        for aid, a in actions_p.items():
            inbound_ids_by_base.setdefault(str(a.get("to")), []).append(aid)

       
        inserts_to: Dict[str, Dict[str, int]] = {} # this will track our inserts to each base
        inserts_from: Dict[str, Dict[str, int]] = {} #this will track our inserts from each base
        eff_orig_touched: Dict[str, bool] = {} #this will track if our effective touched the base originally, marking it for change

        #maps our effective transfers to where they are going and coming from, passed from earlier computations
        for tr in (effective or []):
            k = tr.get("kind") #likely to be "insert", could be lock or leave
            fr = str(tr.get("from"))
            to = str(tr.get("to"))
            addv = PhaseMath.vec(tr.get("L", 0), tr.get("H", 0), tr.get("R", 0)) #the actual vectors for what is being moved

            # only inserts affect our next start, locks and leaves just mark the bases as touched by original effective
            if k == "insert":
                inserts_to[to]   = PhaseMath.add(inserts_to.get(to, PhaseMath.vec()), addv)
                inserts_from[fr] = PhaseMath.add(inserts_from.get(fr, PhaseMath.vec()), addv)
            else:
                if fr:
                    eff_orig_touched[fr] = True
                if to:
                    eff_orig_touched[to] = True
        #We gather  all bases mentioned in original start, end snapshot, inserts and effective touched
        all_bases = set(start_orig_p1.keys()) | set(end_p.keys()) | set(inserts_to.keys()) | set(inserts_from.keys()) | set(eff_orig_touched.keys())

        # this will be our next start snapshot, possible and audit trail
        next_start: Dict[str, Any] = {} # this is our next start snapshot
        audit: Dict[str, Any] = {} # this is our audit trail of how we got there, could be useful for debugging or display later

        # for each base we determine if we can be certain of its numbers or not
        for b in sorted(all_bases):
            inbound = inbound_ids_by_base.get(b, []) #list of inbound action ids to this base
            all_inbound_ll = all(dmap.get(i, "leave") in ("leave", "lock") for i in inbound) #check if all inbound are leave or lock
            any_inbound_del = any(dmap.get(i, "leave") == "delete" for i in inbound) #check if any inbound are delete
            # check if original effective touched this base
            touched_by_orig = bool(eff_orig_touched.get(b, False))
            # branch is used for audit trail
            branch = None
            addv = PhaseMath.vec()
            subv = PhaseMath.vec()

            # the logic here is that if the base was not touched by original effective moves, all inbound are leave/lock and none are delete then we can be certain of its numbers
            # we then take the original start for phase 1 and adjust it by inserts only,
            if (not touched_by_orig) and all_inbound_ll and (not any_inbound_del):
                # we use deepcopy to avoid mutating our original data
                candidate = deepcopy(start_orig_p1.get(b, {"blue": PhaseMath.vec(), "red": PhaseMath.vec()}))
                #adjust numbers based on inserts
                addv = inserts_to.get(b, PhaseMath.vec()) 
                subv = inserts_from.get(b, PhaseMath.vec())
                # and ensure we don't go negative with a clamp
                candidate["blue"] = PhaseMath.clamp_nonneg(PhaseMath.sub(PhaseMath.add(candidate["blue"], addv), subv))
                # we use deepcopy to avoid mutating our original data               
                end_b = deepcopy(end_p.get(b, {"blue": PhaseMath.vec(), "red": PhaseMath.vec()}))
                # if our candidate doesn't match the end snapshot we have an inconsistency likely from deletes affecting the base so we fallback to end snapshot
                if (not PhaseMath.eq(candidate["blue"], end_b.get("blue", PhaseMath.vec()))) or (not PhaseMath.eq(candidate.get("red", PhaseMath.vec()), end_b.get("red", PhaseMath.vec()))):
                    base_snap = end_b
                    branch = "end(p)|consistency"
                else:
                    base_snap = candidate
                    branch = "orig±inserts_only"
            else:
                base_snap = deepcopy(end_p.get(b, {"blue": PhaseMath.vec(), "red": PhaseMath.vec()}))
                branch = "end(p)"

            next_start[b] = base_snap
            #assign our audit values finally
            audit[b] = {
                "branch": branch,
                "orig_p1": deepcopy(start_orig_p1.get(b, {"blue": PhaseMath.vec(), "red": PhaseMath.vec()})),
                "inserts_to_b": addv,
                "inserts_from_b": subv,
                "end_p": deepcopy(end_p.get(b, {"blue": PhaseMath.vec(), "red": PhaseMath.vec()})),
                "checks": {
                    "touched_by_effective_original": touched_by_orig,
                    "all_inbound_ll": all_inbound_ll,
                    "any_inbound_del": any_inbound_del,
                }
            }

        #And finally we resolve control situations where both sides are present
        next_start = AdviseSupport.resolve_control(next_start, meta)

       
        possible = {}

        # lastly in this loop we determine if any bases are uncertain, meaning both sides are present, we mark them as uncertain in possible for further processing
        for bname, sides in next_start.items():
            if PhaseMath.sum_counts(sides.get("blue", PhaseMath.vec())) > 0 and PhaseMath.sum_counts(sides.get("red", PhaseMath.vec())) > 0:
                possible[bname] = {"note": "uncertain"}
        # our return captures the next start, whats uncertain and a full audit trail
        return next_start, possible, audit
