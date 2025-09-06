The following is the current gamestate in JSON format, you are instructed to interpret it in the following way:

LER is important: This is the figure we wish to improve.
Ignore 'bases' as these are simply an expression of the current map screen and not petinent to the final result.
'actions' is very important, this is the section which shows all moves made. It is critical to analyse to improve current LER.
Within actions are 3 phases of the game: '1', '2' and '3'.
Within each phase are the listed actions. Each has:
	'id': the move id within the phase. (id: 1 would be the first move of the phase)
	'from': Which base blue troops are sent from in the move.
	'to': Which base the troops are ordered to move to in the move.
	'L', 'H', 'R': Correlates to Light, Heavy and Ranged. This is how many of each unit type are committed to the move.
	'locked': This is true or false and denotes whether a move is locked for use in future generations of the DEAP algorithm.

Use this information to correctly interpret the JSON file and then use it as well as the 'starting map and scenario' and 'global context' both when deciding what strategy filenames is suitable or when you are making 'Advice Instructions for human'.