import json
from pathlib import Path
from typing import Any, Dict, Union, Optional, List
from agent.decision_logic.run_agent.graph.state import ChatState


# all of our reading/parsing logic in one place
class Readers:
    #json file reader
    @staticmethod
    def read_json(path: Union[str, Path]) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    # specifically built to read our prompts from markdown, with or without .md
    @staticmethod
    def read_prompt(prompts_dir: Union[str, Path], name: str) -> str: #Union allows str or Path
        p = Path(prompts_dir) / name
        if not p.exists():
            p = Path(prompts_dir) / (name if name.endswith(".md") else f"{name}.md")
        try:
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""
    
    # generic text file reader
    @staticmethod
    def read_text(path: Union[str, Path]) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""
    
    # only used here, this flattens any object to a string
    @staticmethod
    def _flatten(obj: Any) -> str:
        if obj is None:
            return ""
        if isinstance(obj, (str, bytes)):
            return obj.decode("utf-8", errors="ignore") if isinstance(obj, bytes) else obj
        if isinstance(obj, (int, float, bool)):
            return str(obj)
        if isinstance(obj, dict):
            return "\n".join([Readers._flatten(v) for v in obj.values()])
        if isinstance(obj, list):
            return "\n".join([Readers._flatten(x) for x in obj])
        return str(obj)

    # only used here, this finds JSON candidates in a string
    @staticmethod
    def _find_json_candidates(s: str) -> List[str]:
        out = []
        i = 0
        n = len(s)
        while i < n:
            try:
                start = s.index("{", i) #we are checking for {
            except ValueError:
                break
            depth = 0 # we use depth to track nested {}
            buf = [] #we use a buffer to build our JSON candidate
            j = start
            while j < n: #track positions until the end }
                ch = s[j] #current character
                if ch == "{": 
                    depth += 1 #increase depth for nested {
                if depth > 0:
                    buf.append(ch) #add character to buffer if inside JSON object
                if ch == "}":
                    depth -= 1 #decrease depth for nested }
                    if depth == 0:
                        out.append("".join(buf)) #complete JSON candidate
                        i = j + 1
                        break
                j += 1
            else:
                break
            #We return all candidates found
        return out

    #The big method: extract a JSON object from arbitrary text
    @staticmethod
    def extract_json(text: Any) -> Optional[Dict[str, Any]]:
        # Flatten input to string if string
        s = Readers._flatten(text)
        if not s:
            return None

        #if it's already JSON, return it
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        # find our JSON candidates
        candidates = Readers._find_json_candidates(s)
        if not candidates:
            return None

        #declare parsed for valid JSON objects
        parsed = []
        for c in candidates:
            try:
                obj = json.loads(c) #try to parse
                if isinstance(obj, dict):
                    parsed.append(obj) #only append if dict
            except Exception:
                continue

        if not parsed:
            return None

        # We prefer for this to be a decisions object if we can find one
        for obj in parsed:
            if "decisions" in obj:
                return obj

        # Otherwise, return the last one
        return parsed[-1]

    # We use this method to prepare a selection context for the selection agent
    @staticmethod
    def build_selection_context(state: ChatState) -> Dict[str, Any]:

        # check for raw game state
        game_raw = getattr(state, "game_state_raw", None)

        #otherwise try to read from file
        if game_raw is None:
            base_dir = getattr(state, "game_state_dir", "game_state_experiment")
            filename = getattr(state, "game_state_filename", "final_game_state.json")
            try:
                game_raw = Readers.read_json(base_dir, filename)
            except Exception:
                game_raw = None

        if not isinstance(game_raw, dict):
            return {"warning": "No game_state available"}

        # We grab only the ler, the phases and the actions.
        meta = game_raw.get("meta", {})
        phases = game_raw.get("phases", {})
        p1 = phases.get("1", {}) if isinstance(phases, dict) else {}

        selection_context = {
            "meta": {
                "map": meta.get("map"),
                "ler": meta.get("ler"),          # tie-break/side favour etc.
                "notes": meta.get("notes"),
            },
            "phase_1": {
                "start": p1.get("start"),        # who holds what / unit counts
                "orig_actions": p1.get("orig_actions"),  # planned transfers
            }
        }
        return selection_context