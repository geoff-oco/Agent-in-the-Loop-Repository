from typing import Dict
from helpers.helpers import Helpers
from langchain_core.tools import tool
from pydantic import BaseModel, Field, ConfigDict
import json


# Our tool call schema for loading markdown strategies
class LoadMarkdownsArgs(BaseModel):

    # ChatGPT is pretty strict of late with tool calls, this helps the api accept it.
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(description="Exact strategy filename chosen from the allowed list.")


# Our tool decorator for loading markdown strategies
@tool("load_markdowns", args_schema=LoadMarkdownsArgs, return_direct=False)
def load_markdowns(filename: str) -> str:
    """Our tool call function for the LLM to select a strategy"""

    # Retrieve the list of allowed names
    allowed = Helpers.get_allowed_names()
    if filename not in allowed:  # not allowed, return empty result
        return json.dumps({"selected_names": [], "selected_texts": {}}, ensure_ascii=False)

    # Grab our directory for filenames
    base = Helpers.get_strategy_dir()
    file_path = f"{base}/{filename}"  # Append directory to filename
    try:
        # Grab our strategy names and contents
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        # If the file cannot be read, return an empty result
        return json.dumps({"selected_names": [], "selected_texts": {}}, ensure_ascii=False)

    # Build our result, the selected strategy
    result: Dict[str, Dict[str, str]] = {
        "selected_names": [filename],
        "selected_texts": {filename: content},
    }
    print(f"selected startegy: {result['selected_names']}")
    return json.dumps(result, ensure_ascii=False)
