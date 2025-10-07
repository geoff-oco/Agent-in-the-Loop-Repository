# Advise Instructions (Phase Decisioning)

## Goal
Given the current phase `start` state and the list of original `orig_actions`, decide for **each original action id** whether to:
- `"leave"` — keep and execute the original transfer as-is this phase.  
- `"lock"` — execute the transfer **and mark it immutable for next phases** (commit to it).  
- `"delete"` — remove the original transfer (its budget returns to the source for inserts).

Also, optionally propose **`inserts`** (new transfers) within budgets.

Return **STRICT JSON ONLY** using the Output schema below.

---

## Inputs (provided in the prompt)
- `phase` (1..3)  
- `start` (current phase start snapshot)  
- `orig_actions` (dict keyed by id → `{id, from, to, L, H, R, locked}`)  
- `meta` (map; tie-break rules via `ler.favour`)  
- `SUMMARY` (3 lines)  
- `STRATEGY NOTES` (short strategy text chosen earlier)

You MUST consider both `STRATEGY NOTES` and `SUMMARY` when making decisions.

---

## Overarching Strategy Points
- **Red2** is the most fortified and difficult base to capture, requiring large unit commitments.
- **Red2** is best attacked from **Red3** once Red3 is secured.

---

## Constraints (mirror server-side validation)
- **Exactly one decision per original id.** Every original action id must appear once with a decision in `{"leave","lock","delete"}`.  
- **Dynamic inserts cap:** `cap = max(0, 5 - count_of(leave_or_lock))`. You may propose up to `cap` inserts (propose fewer if none are impactful/Legal).  
- **Budgets:** Originals execute first. Inserts use the **remaining** per-source Blue budget (START-of-phase) after accounting for executed `leave/lock`.  
- **Clamping:** Insert vectors must be non-negative integers. Over-budget or zero-result inserts will be nullified.  
- **No contested bases** after resolution; ties break by `meta.ler.favour`.  
- **Strict JSON:** Output exactly one JSON object and nothing else.

### Legality checklist for inserts (all must be true)
1) **Source ownership:** Source base had **Blue > 0 at START** of this phase (not acquired later this phase).  
2) **Positive integer vector:** `L + H + R > 0`, each is a non-negative integer.  
3) **Budget respect:** Totals across all inserts from a source do **not** exceed that source’s START-of-phase Blue budget **after** applying `leave/lock`.  
4) **One-hop only:** Use the given base names; **do not invent** new nodes.  
5) **No duplicates / trivial:** Avoid duplicate inserts and `0/0/0` vectors.

---

## Decision Order
Evaluate each original action id independently in this order:
1) **LOCK** if any **LOCK MANDATE** is met.  
2) **LEAVE** if useful and commitment is not warranted.  
3) **DELETE** only when the action harms the plan or frees clearly needed budget.

Global tie-break hierarchy: `lock` **>** `leave` **>** `delete`.

---

## LOCK MANDATES (hard rules)
You **MUST** choose `"lock"` for an original action if **any** of the following are true:

- **High-impact push (heavy):** `H ≥ 5` (Blue Heavy moved by the original).  
- **High-impact total:** `(L + H + R) ≥ 8` moved by the original.  
- **Critical node push:** The target is **Red1** or **Red3** **and** (`H ≥ 3` **or** `(L + H + R) ≥ 5`).  
- **Already locked:** The original has `locked: true` in `orig_actions` (maintain commitment unless deletion is clearly required by strategy).

If **multiple mandates** apply across several actions, you may still `lock` all of them if legal; do **not** downgrade to `leave` when a mandate is met.

---

## When to LEAVE
Use `"leave"` when the action is helpful but flexibility next phase is valuable:
- The effect is good but not decisive, or depends on opponent uncertainty.  
- You anticipate adapting based on this phase’s results or future budgets.

---

## When to DELETE
Use `"delete"` when the original is misaligned with strategy or creates poor trades:
- Sends units into low-value nodes.  
- Conflicts with higher-priority locks/leaves from the same source.  
- Use deletes to **free budget** for smarter inserts (see Inserts Policy).

---

## Inserts Policy (quality over quantity)
- **SHOULD insert when (leave/lock) ≤ 2** or **No actions in the current Phase**, unless **no Legal** insert improves Blue’s position.  
- Prefer a small number of **high-impact** inserts aligned to chokepoints/critical paths.  
- Never exceed per-source remaining budgets; keep vectors positive.
- **Red2 minimum insert rule**: When proposing an **insert** to **Red2**, only do so if it passes the **Legality checklist** and required units are **available**. The insert must send **at least 4 total units** (`L+H+R ≥ 4`). **Prioritise Heavies**, then **Ranged** (H → R). If you cannot reach 4 with legally available H/R, **do not propose** this insert.  
- **Consolidate for Red2:** Prefer **one** legal, consolidated insert to **Red2** (meeting the ≥4 and H→R rule) over multiple small pushes. Delete or downgrade small originals to free budget, then propose the single consolidated insert if legal.
- Set `locked: true` on inserts **only** when commitment is essential.
- If any proposed insert to **Red2** is `< 4` total units, **revise or remove** it.

---

## Final Self-Check (before you output JSON)
- For every original action that meets a **LOCK MANDATE**, confirm you chose `"lock"`.  
- If you output **zero** locks but any mandate was met, **revise decisions** to include the required locks.  
- Ensure the number of inserts ≤ dynamic `cap`.  
- Ensure all inserts pass the **Legality checklist**.

---

## Output (STRICT JSON)
Return ONLY:
```json
{
  "phase": <int>,
  "decisions": [
    {"id": <int>, "decision": "leave|lock|delete"}
  ],
  "inserts": [
    {"from": "<name>", "to": "<name>", "L": <int>, "H": <int>, "R": <int>, "locked": <bool>}
  ]
}
