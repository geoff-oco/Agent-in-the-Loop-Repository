#os for file operations, glob for file pattern matching, json for JSON handling
import os
import glob
import json
from typing import List, Dict, Any, Optional
from helpers.helpers import Helpers

class Readers:
    @staticmethod
    def extract_json(text: str) -> Optional[Dict[str, Any]]: #used in prepare_select node to extract JSON from tool response
        try:
            return json.loads(text)
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1]) # try to parse the substring as JSON
            except Exception:
                return None
        return None

    @staticmethod
    def read_json_file(path: str) -> Dict[str, Any]: #loads the game state from JSON file
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def read_markdowns(names: List[str]) -> Dict[str, str]: #reads our markdowns for strategies to a Dict
        out: Dict[str, str] = {}
        root = Helpers.get_strategy_dir()
        for n in names:
            p = os.path.join(root, n)
            try:
                with open(p, "r", encoding="utf-8") as f:
                    out[n] = f.read().strip()
            except Exception:
                pass
        return out

    @staticmethod
    def read_prompt(directory: str, filename: str) -> str: #reads our various prompts that structure our LLM messages
        path = os.path.join(directory, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
            return ""
        except Exception:
            return ""

    @staticmethod
    def list_markdowns(directory: str) -> List[str]: #this grabs all of the filenames of strategies to give to the LLM for tool call
        try:
            paths = glob.glob(os.path.join(directory, "*.md"))
            names = [os.path.basename(p) for p in paths]
            names.sort()
            return names
        except Exception:
            return []

