import os
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal

class ChatState(BaseModel):
    model: str = Field(default=os.getenv("MODEL_NAME", "gpt-4.1-nano")) #our model from env
    prompts_dir: str = Field(default=os.getenv("PROMPTS_DIR", "./prompts")) # our prompts directory
    strategies_dir: str = Field(default=os.getenv("STRATEGIES_DIR", "./strategies")) #our strategy directory
    game_state_path: str = Field(default=os.getenv("GAME_STATE_PATH", "./game_state")) # our game state directory
    game_state_raw: Dict[str, Any] = Field(default_factory=dict) #to store the actual raw game state found.
    mode: Literal["detail", "simple"] = Field(default="detail") # a toggle to decide the mode of operation
    simple_output: Dict[str, Any] = Field(default_factory=dict) # stores the simple output for simple mode
    runtime: Dict[str, Any] = Field(default_factory=dict) # stores our runtime for detail mode, usd in operations and output
    selected_names: List[str] = Field(default_factory=list) # a list of strategy names found in dir
    selected_texts: Dict[str, str] = Field(default_factory=dict) # the selected strategy
    messages: List[Any] = Field(default_factory=list) #messages to and from LLM
    errors: List[str] = Field(default_factory=list) # any errors
    current_phase: int = 1 # phase counter for detailed mode
    last_structured: Dict[str, Any] = Field(default_factory=dict) # last structured response from LLM
    last_reply: Optional[str] = None # last raw reply from LLM
