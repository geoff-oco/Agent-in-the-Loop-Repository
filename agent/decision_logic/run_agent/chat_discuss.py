from pathlib import Path
import json
from datetime import datetime
from typing import Optional
from langchain_openai import ChatOpenAI
from helpers.readers import Readers


# Private method to resolve the game state path
def _resolve_game_state_path(json_filename: str, base_dir: Optional[str] = None) -> Path:

    # Pull from environment variable if not provided
    root = Path(base_dir or "./game_state")
    # If the provided path is a file, use its parent directory
    base_dir = root if root.is_dir() or not root.suffix else root.parent
    # Append filename to the base directory
    return (base_dir / json_filename).resolve()


# Exposed method to discuss strategy based on game state and user question
def discuss_strategy(json_filename: str, user_question: str) -> str:

    gs_path = _resolve_game_state_path(json_filename)  # Load the game state from the specified JSON file
    game_state = Readers.read_json(gs_path)  # Load that file content into a structured object
    game_state_str = json.dumps(game_state, ensure_ascii=False, indent=2)  # Pretty print it for the model

    advice_dir = Path("agent_replies")  # Directory to store advice files
    advice_dir.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists
    advice_path = advice_dir / (Path(json_filename).stem + ".txt")  # Advice file path based on JSON filename
    if not advice_path.is_file():
        return "No advice file found."  # Hard check to ensure it exits gracefully if no strategy exists

    if advice_path.exists():
        advice_text = advice_path.read_text(encoding="utf-8")  # Read existing advice text
    else:
        return "No advice file found."  # If no advice file, return early

    is_simple = (
        Path(json_filename).name.lower().startswith("simple")
    )  # Determine if the scenario is simple based on filename
    prompt_name = "Simple_Reading.md" if is_simple else "ReadingJSON.md"  # Choose prompt based on scenario complexity
    reading_prompt = Readers.read_prompt("./prompts", prompt_name)  # Read the appropriate prompt template
    context_prompt = Readers.read_prompt("./prompts", "quick_chat_context.md")  # Read additional context prompt

    # Construct the user content for the model
    parts = [
        "The Game State below is what we started with:\n\n",
        reading_prompt.strip(),
        "\n\n--- GAME STATE (read-only) ---\n",
        game_state_str,
        "\n\nThe following is the advice the model gave in regards to that gamestate:\n",
        advice_text.strip(),
        "\n\nHere is some context about the game and your role:\n",
        context_prompt.strip(),
        "\n\nThe user wants to know, regarding the advice given:\n",
        (user_question or "").strip(),
        "\n\nConsidering all information given you, provide a concise, 3-4 sentence answer to help the user improve their strategy. ",
    ]
    user_content = "".join(parts).strip()

    # Initialize the language model, chat completion used for discussion
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.2, max_tokens=800)
    ai = llm.invoke([{"role": "user", "content": user_content}])
    model_answer = getattr(ai, "content", None) or getattr(ai, "output_text", "") or ""

    # Timestamp for entry
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = "Model/User Strategy Discussion:"
    block = []
    # If the header isn't already present, add it
    if header not in advice_text:
        block.append("\n" + header + "\n")

    # Append the new Q&A to the block
    block.extend([f"\n[{now}] User: {user_question.strip()}", f"\n[{now}] Ares: {model_answer.strip()}\n"])

    # Write back the updated advice text with the new discussion appended
    advice_path.write_text((advice_text + "".join(block)).strip() + "\n", encoding="utf-8")
    return model_answer
