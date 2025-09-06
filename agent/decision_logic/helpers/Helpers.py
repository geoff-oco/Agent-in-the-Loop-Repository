import os
from typing import List, Optional
from langchain_ollama import ChatOllama

class Helpers:
    _strategy_dir: str = "./strategies" #default strategy directory
    _allowed_names: List[str] = [] #list of allowed strategy names for tool calls

    @staticmethod
    def log(msg: str) -> None:
        print(f"[agent] {msg}")

    #getters and setters for strategy_dir and allowed_names within state
    @staticmethod
    def set_strategy_dir(path: str) -> None:
        Helpers._strategy_dir = path

    @staticmethod
    def get_strategy_dir() -> str:
        return Helpers._strategy_dir

    @staticmethod
    def set_allowed_names(names: List[str]) -> None:
        Helpers._allowed_names = list(names)

    @staticmethod
    def get_allowed_names() -> List[str]:
        return list(Helpers._allowed_names)

    # Function to get a LangChain LLM instance using Ollama from environment variables or parameters, used in calls to LLM
    @staticmethod
    def get_langchain_llm(base_url: Optional[str], model: Optional[str]):
        url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        mdl = model or os.getenv("MODEL_NAME", "llama3.1:8b")
        return ChatOllama(base_url=url, model=mdl, temperature=0)
