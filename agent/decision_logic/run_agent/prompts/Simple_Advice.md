TASK

Given:

\- The SIMPLE JSON (see Simple\_Reading.md),

\- Computed hints (net movement and inferred outcomes),

\- Selected strategy notes,

write structured advice for EACH PHASE and EACH RED BASE.



CONTENT RULES

For each phase p and base in \[red1, red2, red3], produce:

\- summary: how successful the moves to this base were in phase p

\- lock: what kinds of moves to keep/lock next time (e.g., heavy-forward, consolidated ≥4 total, sources that performed well)

\- delete: what to consider removing or reducing; suggest where to reallocate and why

\- insert: if Blue has unallocated units, where to add an extra move, with a brief unit mix rationale



STRATEGY NOTES

Strategy should maximise red losses while minimising blue losses, consider the following when giving advice:
- Light: Fast, 4HP, 2DMG, Attack\_Range: 1

\- Heavy: Slow, 4HP, 4DMG, Attack\_Range: 1

\- Ranged: Slow, 1HP, 1DMG, Attack\_Range: 3

\- Ranged supports Heavy well

\- Light needs support from other units

\- Ranged needs support from other units

\- Red2 is best attacked from Red3

\- Red Units only defend their base, they \*\*NEVER\*\* attack blue held bases



PROSE RULES

\- For summary produce 2-3 sentences

\- For lock|delete|insert produce 2-3 lines

\- For lock|delete|insert always consider best units in advice reference by name.



Also produce:

\- A global \*\*summary\*\* (3 lines, one per phase) at the top, concise and goal-focused.

\- A global \*\*rationale\*\* (3–6 sentences) at the end, explaining why this advice strengthens Blue’s position and key tradeoffs/risks.



Keep prose compact, specific, and grounded in the observed deltas and p→p+1 outcomes.



STRICT JSON OUTPUT

Return exactly this schema:

{

&nbsp; "mode": "simple",

&nbsp; "meta": {"ler\_favour": "Red|Blue|Neutral", "ler": {"blue": 1.24, "red": 1.0}},

&nbsp; "summary": "Line1\\nLine2\\nLine3",

&nbsp; "phases": \[

&nbsp;   {

&nbsp;     "phase": 1,

&nbsp;     "bases": \[

&nbsp;       {"name":"red1","summary":"...","lock":"...","delete":"...","insert":"..."},

&nbsp;       {"name":"red2","summary":"...","lock":"...","delete":"...","insert":"..."},

&nbsp;       {"name":"red3","summary":"...","lock":"...","delete":"...","insert":"..."}

&nbsp;     ]

&nbsp;   },

&nbsp;   {"phase": 2, "bases": \[...]},

&nbsp;   {"phase": 3, "bases": \[...]}

&nbsp; ],

&nbsp; "rationale": "3–6 sentences explaining the overall why and tradeoffs.",

&nbsp; "notes": "Optional global notes"

}

Populate meta.ler\_favour from the input.

Copy meta.ler dict from the input (contains blue/red ratio values).

No extra keys. No markdown outside JSON.



