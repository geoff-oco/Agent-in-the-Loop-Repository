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

## Usage Guide

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-org>/agent-in-the-loop.git
   cd agent-in-the-loop

2. System Files (local only)

Place the Unity build under system_files/unity_build/

Store maps/configs under system_files/microrts_assets/

Store DEAP run logs/outputs under system_files/deap_outputs/

Add OCR screenshots here for experiments

⚠️ Do not commit large binaries to Git. Use Git LFS or keep them local.

3. Development Flow

Start prototypes in /experiments/prototypes/

Promote stable code into /agent/ submodules

Keep static context docs in /project_context/

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