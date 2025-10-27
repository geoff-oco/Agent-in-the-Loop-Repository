from dotenv import load_dotenv  # For the API Key to load

load_dotenv()
import os, glob, copy
from typing import Any, List
from langchain_openai import ChatOpenAI


# Most generic class of helpful functions used throughout pipeline
class Helpers:

    # These are set when list_markdowns() is called
    _strategy_dir: str = "./strategies"
    _allowed_names: List[str] = []

    # Method to list markdowns in a directory and store them in class vars
    @staticmethod
    def list_markdowns(directory: str) -> List[str]:
        Helpers._strategy_dir = directory
        paths = sorted(glob.glob(os.path.join(directory, "*.md")))
        names = [os.path.basename(p) for p in paths]  # Just the file names
        Helpers._allowed_names = names
        return names

    # Simple call to check against allowed names in class
    @staticmethod
    def get_allowed_names() -> List[str]:
        return list(Helpers._allowed_names)

    # Simple call to pull the strategy directory
    @staticmethod
    def get_strategy_dir() -> str:
        return Helpers._strategy_dir

    # Our method for assigning our LLM
    @staticmethod
    def get_langchain_llm(
        model: str,
        temperature: float = 0.0, # Toggled higher for prose or lower for JSON
        max_tokens: int = 800,
    ):
        # Force JSON-only output so the model cannot echo the input or add prose
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    # Quick deep copy so it doesnt need to be imported everywhere
    @staticmethod
    def dcopy(x: Any) -> Any:
        return copy.deepcopy(x)

    # ---------- Simple Path helpers ----------

    # Used to determine if we are going simple or diving into detail
    @staticmethod
    def get_mode_from_gamepath(path: str) -> str:
        name = os.path.basename(str(path)).lower()
        return "simple" if name.startswith("simple") else "detail"
