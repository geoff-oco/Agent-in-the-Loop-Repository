import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple


class AgentBridge:
    def __init__(self):
        # Calculate absolute project root from current file location
        # agent/visualisation/agent_bridge.py -> project root is 2 levels up
        self.project_root = Path(__file__).parent.parent.parent
        print(f"Project root: {self.project_root}")

        # Set absolute paths
        self.screen_reading_output_dir = self.project_root / "agent" / "screen_reading" / "output"
        self.agent_dir = self.project_root / "agent" / "decision_logic" / "run_agent"
        self.agent_game_state_dir = self.agent_dir / "game_state"  # Agent's local game_state directory

        print(f"Screen reading output dir: {self.screen_reading_output_dir}")
        print(f"Agent game state dir: {self.agent_game_state_dir}")
        print(f"Agent directory: {self.agent_dir}")

    def find_latest_session_file(self) -> Optional[Path]:
        # Find the most recent session folder and its game_state.json
        try:
            print(f"Looking for session directories in: {self.screen_reading_output_dir}")

            if not self.screen_reading_output_dir.exists():
                print(f"Screen reading output directory does not exist: {self.screen_reading_output_dir}")
                return None

            # Look for both 'session_*' and 'game_session_*' patterns
            session_dirs = [d for d in self.screen_reading_output_dir.iterdir()
                          if d.is_dir() and (d.name.startswith('session_') or d.name.startswith('game_session_'))]

            print(f"Found session directories: {[d.name for d in session_dirs]}")

            if not session_dirs:
                print("No session directories found")
                return None

            # Sort by modification time, get latest
            latest_session = max(session_dirs, key=lambda d: d.stat().st_mtime)
            print(f"Latest session directory: {latest_session}")

            game_state_file = latest_session / "game_state" / "game_state.json"

            if game_state_file.exists():
                print(f"Found latest game state: {game_state_file}")
                return game_state_file
            else:
                print(f"Game state file not found in {latest_session}")
                print(f"Looking for: {game_state_file}")

                # Debug: list contents of session directory
                try:
                    print(f"Session directory contents: {list(latest_session.iterdir())}")
                    if (latest_session / "game_state").exists():
                        print(f"Game state directory contents: {list((latest_session / 'game_state').iterdir())}")
                except Exception as debug_e:
                    print(f"Error listing directory contents: {debug_e}")

                return None

        except Exception as e:
            print(f"Error finding latest session: {e}")
            return None

    def bridge_to_agent(self, use_simple_path: bool = True) -> Optional[str]:
        # Copy latest session file to agent location with appropriate naming
        latest_file = self.find_latest_session_file()
        if not latest_file:
            return None

        # Create agent game state directory if it doesn't exist
        self.agent_game_state_dir.mkdir(parents=True, exist_ok=True)

        # Choose filename based on desired path (simple vs detail)
        if use_simple_path:
            bridge_filename = "simple_game_state.json"
        else:
            bridge_filename = "game_state.json"

        bridge_path = self.agent_game_state_dir / bridge_filename

        try:
            # Copy the file
            shutil.copy2(latest_file, bridge_path)
            print(f"Bridged game state to agent: {bridge_path}")
            return bridge_filename
        except Exception as e:
            print(f"Error bridging file to agent: {e}")
            return None

    def call_agent(self, filename: str) -> Optional[str]:
        # Call the agent as a separate subprocess to avoid import/threading issues
        try:
            print(f"Attempting to call agent with filename: {filename}")
            print(f"Agent directory: {self.agent_dir}")

            if not self.agent_dir.exists():
                print(f"Agent directory not found: {self.agent_dir}")
                return None

            # Create a simple Python script to call the agent
            agent_script = f'''
import sys
import os
from pathlib import Path

# Load environment variables from project root
from dotenv import load_dotenv
load_dotenv(r"{self.project_root / '.env'}")

# Add agent directory to path
sys.path.insert(0, r"{self.agent_dir}")

# Change to agent directory
os.chdir(r"{self.agent_dir}")

# Import and call the agent
from run_agent import run_agent
result_path = run_agent("{filename}")
print(f"AGENT_RESULT_PATH: {{result_path}}")
'''

            # Write the script to a temporary file
            temp_script = self.project_root / "temp_run_agent.py"
            temp_script.write_text(agent_script, encoding='utf-8')

            try:
                # Run the agent script as a subprocess
                result = subprocess.run(
                    [sys.executable, str(temp_script)],
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )

                # Parse the result path from stdout
                result_path = None
                for line in result.stdout.split('\n'):
                    if line.startswith('AGENT_RESULT_PATH:'):
                        result_path = line.replace('AGENT_RESULT_PATH:', '').strip()
                        break

                if result.returncode == 0 and result_path:
                    print(f"Agent completed successfully, result saved to: {result_path}")
                    return result_path
                else:
                    print(f"Agent failed with return code: {result.returncode}")
                    print(f"STDOUT: {result.stdout}")
                    print(f"STDERR: {result.stderr}")
                    return None

            finally:
                # Clean up temporary script
                try:
                    temp_script.unlink()
                except:
                    pass

        except Exception as e:
            print(f"Error calling agent: {e}")
            import traceback
            traceback.print_exc()
            return None

    def read_agent_result(self, result_path: str) -> Optional[str]:
        # Read the agent's generated strategy from the result file
        try:
            # Convert to absolute path if needed
            if not Path(result_path).is_absolute():
                result_file = self.agent_dir / result_path
            else:
                result_file = Path(result_path)

            print(f"Looking for result file: {result_file}")

            if result_file.exists():
                strategy = result_file.read_text(encoding='utf-8')
                print(f"Read strategy from: {result_file}")
                print(f"Strategy length: {len(strategy)} characters")
                return strategy
            else:
                print(f"Agent result file not found: {result_file}")
                # Try alternative locations
                alternative_paths = [
                    self.project_root / result_path,
                    self.agent_dir / "agent_replies" / Path(result_path).name
                ]
                for alt_path in alternative_paths:
                    if alt_path.exists():
                        print(f"Found result file at alternative location: {alt_path}")
                        return alt_path.read_text(encoding='utf-8')
                return None
        except Exception as e:
            print(f"Error reading agent result: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_strategy(self, use_simple_path: bool = True) -> Tuple[bool, Optional[str]]:
        # Complete flow: bridge file, call agent, return strategy
        print("Starting agent strategy generation...")

        # Step 1: Bridge the latest session file
        bridged_filename = self.bridge_to_agent(use_simple_path)
        if not bridged_filename:
            return False, "Failed to bridge game state file to agent"

        # Step 2: Call the agent
        result_path = self.call_agent(bridged_filename)
        if not result_path:
            return False, "Failed to call agent"

        # Step 3: Read the result
        strategy = self.read_agent_result(result_path)
        if not strategy:
            return False, "Failed to read agent result"

        return True, strategy