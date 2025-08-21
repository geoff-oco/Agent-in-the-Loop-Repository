# Agent in the Loop

CSG3101 Final-Year Project — Edith Cowan University  
Group Repository for "Agent in the Loop"

---

## 📌 Project Overview
This project extends the **interactive evolutionary algorithm system** by integrating an **intelligent agent**.  
The agent will interact by **reading the simulation screen (OCR/visual cues)** and reasoning about possible actions, without any file-level integration or Unity-side code.

The repository is structured to support:
- Agent development (screen reading, decision logic, action execution, visualisation)
- Prototyping and experimentation
- Testing for reliability and reproducibility
- Storage of project context and system artefacts (read-only)
- Please maintain clear commenting to support group coding efforts.
---

## 📂 Repository Structure
Agent-in-the-Loop/
├── agent/ # Core agent modules
│ ├── screen_reading/
│ ├── decision_logic/
│ ├── action_execution/
│ ├── visualisation/
│ ├── integration/
│ └── tests/
│
├── experiments/ # Early prototypes
│ └── prototypes/
│
├── system_files/ # Existing project artefacts (read-only)
│ ├── unity_build/
│ ├── microrts_assets/
│ ├── deap_outputs/
│ └── README.md
│
├── project_context/ # Original brief, GECCO paper, static docs
│
├── .gitignore
├── .gitattributes # (Optional) Git LFS rules
├── CONTRIBUTING.md
├── LICENSE
└── README.md


---

## 🚀 Getting Started

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-org>/agent-in-the-loop.git
   cd agent-in-the-loop

2. Where to Work

   New ideas → /experiments/prototypes/

   Stable modules → /agent/

   Tests → /agent/tests/

   Static docs → /project_context/

   System artefacts → /system_files/ (local-only, avoid committing large binaries)

   Branch Naming

      feature/<short-description> → code features

      docs/<short-description> → documentation updates

      Use Pull Requests for merging into main. Keep prototypes separate from production-ready modules.

⚠️ Large Files

   Do not commit Unity builds or large binaries directly.

   If essential, configure .gitattributes with Git LFS.

   Otherwise, store artefacts locally and reference them in system_files/README.md.

