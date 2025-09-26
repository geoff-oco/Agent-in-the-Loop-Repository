SIMPLE JSON SHAPE (read-only)

\- meta.ler.favour indicates tie-break favour (Red|Blue|Neutral).

\- phases: array of {phase, before, after}.

&nbsp; - Each 'before'/'after' has entries for:

&nbsp;   - "blue" (player base), "red1", "red2", "red3"

&nbsp;   - Each entry contains:

&nbsp;       "blue": {L,H,R}  (Blue units at that base)

&nbsp;       "red":  {L,H,R}  (Red units at that base)



INTERPRETING MOVEMENT

\- Per phase p: compute the NET Blue movement INTO each base as (after.blue - before.blue) clamped at ≥0 per component.

\- Battle outcomes are NOT in 'after'. They are implied by the next phase 'before'.

\- Successful offensive pushes typically leave surviving Blue at target in p+1 before; failed ones do not.



SCOPE

\- Consider advisories ONLY for red1, red2, red3 per phase.

\- Track what remains at "blue" across phases (unallocated reserves).

\- Treat movements as block-level; you cannot comment on precise micro routes.



