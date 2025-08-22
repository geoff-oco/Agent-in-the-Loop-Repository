# DEVELOPMENT.md

# Repository Bootstrap for "Agent in the Loop"

## Repository Purpose
This repository supports the CSG3101 "Agent in the Loop" project.  
The system will integrate an intelligent agent capable of observing and acting on the simulation **via the screen interface (OCR/visual cues)**.  

⚠️ Note: We are **not** using file-level access or Unity-side code — all interaction is from the external agent side.  
This repo is for structuring our work and ensuring collaboration across the team.

---

## Repository Structure

Agent-in-the-Loop/
│
├── agent/                      # Core agent modules
│   ├── screen_reading/         # OCR / visual input prototypes
│   ├── decision_logic/         # Reasoning, planning, selection
│   ├── action_execution/       # How the agent applies actions (e.g., inputs)
│   ├── visualisation/          # Agent visualisation, Plots, dashboards, run summaries
│   ├── integration/            # Light glue and config (no Unity code)
│   └── tests/                  # Automated + manual test suites
│
├── experiments/                # Early prototypes & sandboxes
│   └── prototypes/             # Prototypes storage
│
├── system_files/               # Existing project artefacts (read-only in repo)
│   ├── unity_build/            # Executable build + Data/ (DO NOT COMMIT large binaries)
│   ├── microrts_assets/        # Maps/configs if provided (check license)
│   ├── deap_outputs/           # Playback/logs/CSV from runs
│   └── README.md               # What belongs here + size/licensing notes
│
├── project_context/            # Original brief, GECCO paper, static context
│
├── .gitignore
├── .gitattributes              # (Optional) LFS pointers for large binaries
├── CONTRIBUTING.md
├── LICENSE
└── README.md

---

## Contribution Workflow

- **Branching**  
  - `feature/<short-description>` (e.g., `feature/ocr-prototype`, `feature/decision-logic`) 

- **Pull Requests**  
  - All changes merged to `main` via PRs  

- **Prototypes vs Production**  
  - Keep *early tests* in `/experiments/`  
  - Move *refined modules* into `/agent/`  

- **Testing**  
  - Place automated and manual test cases in `/agent/tests/`  
  - Maintain a README in `/tests/` to describe what’s covered  

- **Commenting**  
  - We will get nowwhere if we don't comment our code effectively in a group setting, - please maintain this.
---

## Getting Started

### Prerequisites
- **Git**: For version control and collaboration
- **Python 3.8+**: For agent development and ML libraries
- **Visual Studio Code**: Recommended IDE with extensions
- **Java Runtime**: Required for MicroRTS simulation engine

### 1. Repository Setup
```bash
# Clone the repository
git clone https://github.com/B0rc/Agent-in-the-Loop-Repository.git
cd Agent-in-the-Loop-Repository
```

### 2. Python Virtual Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Verify activation (should show venv path)
which python
```

### 3. Install Development Dependencies
Create `requirements.txt` in the repository root:
```txt
opencv-python>=4.8.0        # Computer vision for screen capture
pytesseract>=0.3.10         # OCR text recognition
numpy>=1.24.0               # Numerical computing
pillow>=10.0.0              # Image processing
matplotlib>=3.7.0           # Plotting and visualization
scikit-learn>=1.3.0         # Machine learning utilities
pygame>=2.5.0               # Game input simulation
pyautogui>=0.9.54           # GUI automation
jupyter>=1.0.0              # Interactive development
pytest>=7.4.0               # Testing framework
black>=23.7.0               # Code formatting
pylint>=2.17.0              # Code linting
```

Then install:
```bash
pip install -r requirements.txt
```

### 4. VS Code Setup

#### Required Extensions
Install these VS Code extensions:
- `ms-python.python` - Python language support
- `ms-python.pylint` - Code linting
- `ms-python.black-formatter` - Code formatting  
- `ms-toolsai.jupyter` - Jupyter notebook support
- `eamodio.gitlens` - Enhanced Git capabilities
- `ms-vscode.hexdump` - Binary file viewing
- `redhat.vscode-xml` - XML support for map files

#### Workspace Configuration
Create `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "./venv/Scripts/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "files.exclude": {
    "Project System Files/**": true
  }
}
```

### 5. Project Structure Creation
```bash
# Create planned directory structure
mkdir agent experiments project_context
mkdir agent/screen_reading agent/decision_logic agent/action_execution
mkdir agent/visualisation agent/integration agent/tests
mkdir experiments/prototypes

# Add placeholder files
echo "# Screen Reading Module" > agent/screen_reading/README.md
echo "# Decision Logic Module" > agent/decision_logic/README.md  
echo "# Action Execution Module" > agent/action_execution/README.md
echo "# Visualisation Module" > agent/visualisation/README.md
echo "# Integration Module" > agent/integration/README.md
echo "# Test Suite" > agent/tests/README.md
echo "# Prototypes Area" > experiments/prototypes/README.md
```

### 6. Virtual Environment Usage

#### Daily Development Workflow
```bash
# Always activate venv before working
cd Agent-in-the-Loop-Repository
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Your terminal prompt should now show (venv)
# Install new packages as needed
pip install package-name

# Deactivate when done
deactivate
```

#### VS Code Python Interpreter
1. Open VS Code in the repository: `code .`
2. Press `Ctrl+Shift+P` (Command Palette)
3. Type "Python: Select Interpreter"
4. Choose `./venv/Scripts/python.exe`

### 7. System Files Setup (Local Only)
- Obtain evolutionary RTS system files from team lead
- Place under `Project System Files/` directory
- Test system: `cd "Project System Files" && RTSViewer.exe`

### 8. Verification
```bash
# Test Python environment
python --version
pip list

# Test repository structure
git status
tree /f  # Windows - shows directory structure
```

### Development Workflow
1. **Always activate venv**: `venv\Scripts\activate`
2. **Create feature branch**: `git checkout -b feature/your-feature`
3. **Start with prototypes**: Work in `experiments/prototypes/`
4. **Move to production**: Stable code goes in `agent/`
5. **Test regularly**: Use `pytest` in `agent/tests/`
6. **Format code**: Run `black .` before commits

## Current System Commands

### Running the Existing Evolutionary RTS System
```bash
# Start Unity visualization frontend
cd "Project System Files"
./RTSViewer.exe

# Run evolutionary algorithm backend
cd "Project System Files/RTSViewer_Data/evolutionary-rts"
./evolutionary-rts.exe

# Run single evolution test
./tests.GameEvolutionOnce.exe
```

### Configuration and Data
- Evolution parameters: `Project System Files/RTSViewer_Data/evolutionary-rts/evo_params.json`
- Experiment results: `Project System Files/RTSViewer_Data/evolutionary-rts/experiments/[timestamp]/`
- Game maps: `Project System Files/RTSViewer_Data/evolutionary-rts/*.xml`

Note: The "Project System Files" directory contains the complete existing evolutionary RTS system that the agent will interact with externally.