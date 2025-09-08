import json
from langchain_core.tools import tool
from helpers.helpers import Helpers
from helpers.readers import Readers

@tool
def load_markdowns(filename: str | list[str]) -> str:
    """Load markdown files from the strategies directory."""
    allowed = set(Helpers.get_allowed_names()) # get the allowed names from helpers

    # if the model passed a single filename (as they sometimes do), keep it if allowed
    if isinstance(filename, str):
        selected = [filename] if filename in allowed else []
    else:
        # if the model passed a list of filenames, filter to only allowed and take the first one
        selected = [n for n in filename if n in allowed][:1]

    texts = Readers.read_markdowns(selected) # read the markdown contents for the selected filenames
    Helpers.log(f"[tools.load_markdowns] allowed: {allowed}, selected: {selected}")
    payload = json.dumps({"selected_names": selected, "selected_texts": texts}) # prepare the JSON payload
    return payload

