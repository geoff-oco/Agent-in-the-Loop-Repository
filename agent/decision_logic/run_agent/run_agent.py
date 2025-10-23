import os
from pathlib import Path
from graph.graph import build_graph
from graph.state import ChatState


# Function to run the agent with a given json filename
def run_agent(json_filename: str) -> str:

    # Initialise our state
    state = ChatState()

    # Set the game state path based on the provided filename
    base = Path(state.game_state_path)
    base_dir = base if base.is_dir() or not base.suffix else base.parent

    full_path = base_dir / json_filename  # Create the full path
    state.game_state_path = full_path.as_posix()  # Assign it to state

    app = build_graph().compile()  # Build Graph

    # Invoke the graph with our state
    final_state = app.invoke(state)

    # Extract the last reply from the final state
    if hasattr(final_state, "last_reply"):
        output_text = (final_state.last_reply or "").strip()  # Get last reply
    else:
        # Fallback if last_reply attribute is missing or a dict
        output_text = str((final_state or {}).get("last_reply", "")).strip()

    # Save the output to a file
    out_dir = Path("agent_replies")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (Path(json_filename).stem + ".txt")
    out_path.write_text(output_text, encoding="utf-8")

    return out_path.as_posix()


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Check if filename argument provided
    if len(sys.argv) < 2:
        print("Usage: python run_agent.py <json_filename>")
        print("Example: python run_agent.py game_state.json")
        sys.exit(1)

    # Get filename from command line
    filename = sys.argv[1]

    # Run the agent
    try:
        result_path = run_agent(filename)
        print(f"\nAgent completed successfully!")
        print(f"Output saved to: {result_path}")

        # Display the output (handle encoding errors for Windows console)
        with open(result_path, "r", encoding="utf-8") as f:
            output_text = f.read()
            try:
                print(f"\n=== Agent Output ===\n{output_text}")
            except UnicodeEncodeError:
                # Windows console can't handle some characters, use ASCII-safe version
                print(f"\n=== Agent Output ===\n{output_text.encode('ascii', errors='replace').decode('ascii')}")
    except Exception as e:
        print(f"Error running agent: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
