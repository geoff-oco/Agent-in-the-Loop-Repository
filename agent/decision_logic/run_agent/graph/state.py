import os
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal


class ChatState(BaseModel):
    model: str = Field(default=os.getenv("MODEL_NAME", "gpt-4.1-nano"))  # LLM model
    prompts_dir: str = Field(default=os.getenv("PROMPTS_DIR", "./prompts"))  # Prompts directory
    strategies_dir: str = Field(default=os.getenv("STRATEGIES_DIR", "./strategies"))  # Strategy directory
    game_state_path: str = Field(default=os.getenv("GAME_STATE_PATH", "./game_state"))  # Game state directory
    game_state_raw: Dict[str, Any] = Field(default_factory=dict)  # Stores raw game state found.
    mode: Literal["detail", "simple"] = Field(default="detail")  # Toggle to decide the mode of operation
    simple_output: Dict[str, Any] = Field(default_factory=dict)  # Stores the simple output for simple mode
    selected_names: List[str] = Field(default_factory=list)  # List of strategy names found in dir
    selected_texts: Dict[str, str] = Field(default_factory=dict)  # The selected strategy
    messages: List[Any] = Field(default_factory=list)  # Messages to and from LLM
    errors: List[str] = Field(default_factory=list)  # Errors
    current_phase: int = 1  # Phase counter for detailed mode
    last_structured: Dict[str, Any] = Field(default_factory=dict)  # Last structured response from LLM
    last_reply: Optional[str] = None  # Last raw reply from LLM
    runtime: Dict[str, Any] = Field(
        default_factory=dict
    )  # Stores our runtime for detail mode, used in operations and output
