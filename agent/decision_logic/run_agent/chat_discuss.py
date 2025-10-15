from pathlib import Path
import json
from datetime import datetime
from typing import Optional
from langchain_openai import ChatOpenAI
from helpers.readers import Readers

# private method to resolve the game state path
def _resolve_game_state_path(json_filename: str, base_dir: Optional[str] = None) -> Path:

    #Pull from environment variable if not provided
    root = Path(base_dir or "./game_state")
    # If the provided path is a file, use its parent directory
    base_dir = root if root.is_dir() or not root.suffix else root.parent
    # Annnd append the filename
    return (base_dir / json_filename).resolve()

# Our main function for chatbot discussion of strategy
def discuss_strategy(json_filename: str, user_question: str) -> str:

    # First we use above method to get the game state path
    gs_path = _resolve_game_state_path(json_filename)
    game_state = Readers.read_json(gs_path) #load that file content into a structured object
    game_state_str = json.dumps(game_state, ensure_ascii=False, indent=2) #Annnnd pretty-print it

    #We then grab the path for our agent replies file
    advice_dir = Path("agent_replies")
    advice_dir.mkdir(parents=True, exist_ok=True)
    #And look for a text file with the same name as our game state
    advice_path = advice_dir / (Path(json_filename).stem + ".txt")
    if not advice_path.is_file():
        return "No advice file found." #first line check if strategy exists and aexit

    if advice_path.exists():
        advice_text = advice_path.read_text(encoding="utf-8")
    else:
        return "No advice file found." #Hard check to ensure it exits gracefully if no strategy exists

    # Important to check if simple or not so we grab the right instructions for interpreting game state
    is_simple = Path(json_filename).name.lower().startswith("simple")
    prompt_name = "Simple_Reading.md" if is_simple else "ReadingJSON.md"
    reading_prompt = Readers.read_prompt("./prompts", prompt_name)
    #Chat context is for chat only, just contains some generic facts about the game like unit stats, etc
    context_prompt = Readers.read_prompt("./prompts", "quick_chat_context.md")

    # Finally, build everything into a big old prompt
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
        "\n\nConsidering all information given you, provide a concise, 3-4 sentence answer to help the user improve their strategy. "
    ]
    user_content = "".join(parts).strip()

    # Not going to use our agent method for llm construction here because its very hard wired for JSON
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.2, max_tokens=800)
    ai = llm.invoke([{"role": "user", "content": user_content}])
    model_answer = getattr(ai, "content", None) or getattr(ai, "output_text", "") or ""

    # Timestamp for entry 
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = "Model/User Strategy Discussion:"
    block = []
    # We check if the header for convo entries is there, add if not
    if header not in advice_text:
        block.append("\n" + header + "\n")

    # Then we append the conversation to the file
    #Now since we pass the entire file each time....we actually have some rudimentory memory of the conversation!
    block.extend([
        f"\n[{now}] User: {user_question.strip()}",
        f"\n[{now}] Ares: {model_answer.strip()}\n"
    ])

    advice_path.write_text((advice_text + "".join(block)).strip() + "\n", encoding="utf-8")
    return model_answer
