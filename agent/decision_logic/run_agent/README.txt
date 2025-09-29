# LangChain GPT Agent – Decision Logic Test

## Overview
This project is a prototype **decision-making agent** built on top of [LangGraph](https://github.com/langchain-ai/langgraph) and [LangChain Core](https://python.langchain.com/).  
The agent processes a game state (stored as JSON) and generates either **detailed advice** or **simple advice** depending on the input file.

**Key features**
- Modular design with phases (math checks, strategy selection, rationale, finalisation).
- Configurable via a `game_state_path` that points to the JSON input.
- Outputs final advice as plain text.

---

## Requirements
Install dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt

###Main dependencies###

langgraph – building and running the decision graph

langchain-core and langchain-openai – LLM integration

openai – OpenAI API client

pydantic – structured state management

python-dotenv – environment variable support


##.env
Place your openai api key in .env at OPENAI_API_KEY

---

## Running the Agent
Use the run_agent function defined in run_agent.py.
It takes the name of a JSON file, resolves it against the game_state_path, executes the agent, and saves the result.

###Example###

from run_agent import run_agent

# Run agent in detail mode
result_path = run_agent("final_game_state.json")

# Run agent in simple mode
result_path = run_agent("simple_demo.json")

Output
The agent writes its reply into: agent_replies/<filename>.txt

---

## Detail vs. Simple Path
Detail Path: Any JSON file name not starting with simple_ triggers the detailed workflow, producing a full multi-phase analysis and rationale by repeatedly feeding the model requests each phase and rigorous validation on responses.

Simple Path: JSON files that start with simple_ trigger the simple workflow, producing a shorter, more direct reply achieved with a single message pass to the model.