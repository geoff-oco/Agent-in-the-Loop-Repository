import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ChatState(BaseModel):
    model: str = os.getenv("MODEL_NAME", "llama3.1:8b") # Default model name from environment variable or fallback
    base_url: Optional[str] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") # Default base URL from environment variable or fallback
    game_state_path: str = "./game_state_experiment/game_state.json" # Path to the game state JSON file
    strategies_dir: str = "./strategies" # Directory containing strategy markdown files
    prompts_dir: str = "./prompts" # Directory containing prompt markdown files
    game_state: Dict[str, Any] = Field(default_factory=dict) # The current game state as a dictionary, parsed from JSON file
    strategy_names: List[str] = Field(default_factory=list) # List of available strategy markdown filenames used in first pass
    selected_names: List[str] = Field(default_factory=list) # List of selected strategy filenames chosen by the LLM in tool call
    selected_texts: Dict[str, str] = Field(default_factory=dict) # Dictionary of selected strategy filename for use in LLM 2nd pass, seem to only return a Dict...
    last_reply: Optional[str] = None # The last reply from the LLM after advising
    errors: List[str] = Field(default_factory=list) # List of error codes encountered during processing
    messages: List[Any] = Field(default_factory=list) # List of all messages exchanged with the LLM, including tool calls

