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

    def find_latest_session_file(self) -> Tuple[Optional[Path], Optional[str]]:
        # Find the most recent session folder and return (file_path, original_filename)
        # Auto-detects enriched (game_state.json) vs simple (simple_game_state.json)
        try:
            print(f"Looking for session directories in: {self.screen_reading_output_dir}")

            if not self.screen_reading_output_dir.exists():
                print(f"Screen reading output directory does not exist: {self.screen_reading_output_dir}")
                return None, None

            # Look for both 'session_*' and 'game_session_*' patterns
            session_dirs = [
                d
                for d in self.screen_reading_output_dir.iterdir()
                if d.is_dir() and (d.name.startswith("session_") or d.name.startswith("game_session_"))
            ]

            print(f"Found session directories: {[d.name for d in session_dirs]}")

            if not session_dirs:
                print("No session directories found")
                return None, None

            # Sort by modification time, get latest
            latest_session = max(session_dirs, key=lambda d: d.stat().st_mtime)
            print(f"Latest session directory: {latest_session}")

            # Check for enriched export first (game_state.json with actions)
            game_state_file = latest_session / "game_state" / "game_state.json"
            if game_state_file.exists():
                print(f"Found enriched game state: {game_state_file}")
                return game_state_file, "game_state.json"

            # Fall back to simple export (simple_game_state.json - OCR only)
            simple_state_file = latest_session / "game_state" / "simple_game_state.json"
            if simple_state_file.exists():
                print(f"Found simple game state: {simple_state_file}")
                return simple_state_file, "simple_game_state.json"

            # Neither found - list contents for debugging
            print(f"No game state file found in {latest_session}")
            try:
                print(f"Session directory contents: {list(latest_session.iterdir())}")
                if (latest_session / "game_state").exists():
                    print(f"Game state directory contents: {list((latest_session / 'game_state').iterdir())}")
            except Exception as debug_e:
                print(f"Error listing directory contents: {debug_e}")

            return None, None

        except Exception as e:
            print(f"Error finding latest session: {e}")
            return None, None

    def generate_strategy(self) -> Tuple[bool, Optional[str]]:
        # Complete flow: find session, copy file, call agent, return strategy
        # Auto-detects enriched (game_state.json) vs simple (simple_game_state.json)
        try:
            print("Starting agent strategy generation...")

            # Step 1: Find latest session file
            result = self.find_latest_session_file()
            if not result or result[0] is None:
                return False, "Failed to find game state file"

            latest_file, filename = result
            print(f"Found latest session file: {filename}")

            # Step 2: Copy file to agent directory
            self.agent_game_state_dir.mkdir(parents=True, exist_ok=True)

            # Clean up old game state files to avoid conflicts
            for old_file in [
                self.agent_game_state_dir / "game_state.json",
                self.agent_game_state_dir / "simple_game_state.json",
            ]:
                if old_file.exists():
                    old_file.unlink()
                    print(f"Removed old file: {old_file.name}")

            # Copy file (preserves filename for agent mode routing)
            bridge_path = self.agent_game_state_dir / filename
            shutil.copy2(latest_file, bridge_path)
            print(f"Bridged {filename} to agent")

            #Copy stats file if present
            stats_source = latest_file.parent.parent / "stats.json"
            if stats_source.exists():
                stats_dest = self.agent_game_state_dir / "stats.json"
                shutil.copy2(stats_source, stats_dest)
                print(f"Stats file bridged to agent game_state directory")
            else:
                print("No stats file found in session (skipping)")

            # Step 3: Run agent subprocess
            if not self.agent_dir.exists():
                return False, f"Agent directory not found: {self.agent_dir}"

            result = subprocess.run(
                [sys.executable, "run_agent.py", filename],
                cwd=str(self.agent_dir),
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                print(f"Agent failed with return code: {result.returncode}")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                return False, f"Agent execution failed: {result.stderr}"

            # Step 4: Parse output path from agent's stdout
            result_path = None
            for line in result.stdout.split("\n"):
                if line.startswith("Output saved to:"):
                    result_path = line.replace("Output saved to:", "").strip()
                    break

            # Fallback to default location if not found in output
            if not result_path:
                result_path = f"agent_replies/{Path(filename).stem}.txt"

            # Convert to absolute path
            result_file = self.agent_dir / result_path if not Path(result_path).is_absolute() else Path(result_path)

            # Step 5: Read strategy from result file
            if not result_file.exists():
                return False, f"Agent output file not found: {result_file}"

            strategy = result_file.read_text(encoding="utf-8")
            print(f"Strategy generated successfully ({len(strategy)} characters)")

            return True, strategy

        except Exception as e:
            print(f"Error in strategy generation: {e}")
            import traceback

            traceback.print_exc()
            return False, f"Strategy generation error: {str(e)}"
