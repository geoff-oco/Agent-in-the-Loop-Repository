Advice Instructions for human

Respond with a concise, readable strategy summary ONLY (no JSON, no code fences):

\- 2 sentences on the overall plan to improve LER, also list current LER.

\- Then bullets per listed move, per phase listing concrete human actions (lock/delete/insert).

\- Finally a 3 sentence summary on changes you have made and why



Human Actions (for you to output, must cover every move in each phase)

Before listing the advice move, please list the move pulled from JSON in the following format (From Base -> Base Committed L:(n), H:(n), R:(n)). Every single move from JSON must be listed and advice given.



When listing the advice moves you must express it in the format suggested.

\*\*Advice Moves\*\*

lock (Locks one of the existing moves for future generations under the DEAP algorithm) Express as: From Base -> Base Commit L:(n), H:(n), R:(n) \*\*Lock\*\*

delete (Deletes this move so it is not included in future DEAP generations) Express as: From Base -> Base Commit L:(n), H:(n), R:(n) \*\*Delete\*\*

insert (insert your own allocation into future allocations, should include an allocation of units and unit types from one base to another) Express as: Move(n)(This is a new move so update numbering appropriately) From Base -> Base Commit L:(n), H:(n), R:(n) \*\*Insert\*\*

edit (Use this to suggest deleting a move and inserting a different move) Express as: Combine syntax of delete and then insert, Head with \*\*Edit\*\*



When inserting you may add moves of your own as it makes sense such as move 4, move 5, etc.

Your advice must account for every move made in every phase from the JSON file, "see Reading JSON".



