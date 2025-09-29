Reading the Game State (JSON)

The game state is provided in a phased schema:

{
"meta": { "timestamp": string, "ler": { "blue": number, "red": number, "favour": "Blue"|"Red"|"Neutral" } },
"phases": \[
{
"phase": 1|2|3,
"start": {
// per-base unit counts at the START of this phase
// Example shape:
// "blue": { "light": int, "heavy": int, "ranged": int }
// "red1": { "blue": {...}, "red": {...} }
// "red2": { "blue": {...}, "red": {...} }
// "red3": { "blue": {...}, "red": {...} }
},
"actions": \[
{ "id": int,
"from": "Blue" | "Red1" | "Red2" | "Red3",
"to":   "Blue" | "Red1" | "Red2" | "Red3",
"L": int, "H": int, "R": int,
"locked": boolean }
],
"after": { ... snapshot at the END of this phase (informational) ... }
},
...
],
"final\_state": { ... units after phase 3; end of scenario ... }
}

Notes

\- L, H, R are non-negative integers.

\- A phase’s start numbers represent available units per base before actions.

\- “Inserts” (your additions) must not exceed the origin base’s available units for that phase.

\- When instructed to produce JSON, return exactly the requested keys and types—no commentary.

 Ignore "after" focus on "ler" "phase", "start", "actions", "final\_state".

