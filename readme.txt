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

### Quick Setup
1. **Clone the repository**
   ```bash
   git clone https://github.com/B0rc/Agent-in-the-Loop-Repository.git
   cd Agent-in-the-Loop-Repository
   ```

2. **Setup Python Environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # macOS/Linux
   
   # Install dependencies (numpy, matplotlib, jupyter, pytest, black, pylint)
   pip install -r requirements.txt
   ```

3. **VS Code Setup (Recommended)**
   
   **Install Extensions:**
   - Via Extensions Panel (Ctrl+Shift+X), search and install:
     - `ms-python.python` - Python support
     - `ms-python.pylint` - Code linting
     - `ms-python.black-formatter` - Code formatting
     - `ms-toolsai.jupyter` - Jupyter notebooks
     - `eamodio.gitlens` - Git integration
   
   **Or via Command Line:**
   ```bash
   code --install-extension ms-python.python
   code --install-extension ms-python.pylint
   code --install-extension ms-python.black-formatter
   code --install-extension ms-toolsai.jupyter
   code --install-extension eamodio.gitlens
   ```
   
   **Open in VS Code:**
   ```bash
   code .
   ```
   
   **Select Python Interpreter:**
   - Press `Ctrl+Shift+P`
   - Type "Python: Select Interpreter"
   - Choose `./venv/Scripts/python.exe`

### Development Workflow
- **Always activate venv**: `venv\Scripts\activate` before coding
- **Branch naming**: `feature/<description>` for features, `docs/<description>` for docs
- **Code locations**:
  - New ideas → `experiments/prototypes/`
  - Stable modules → `agent/`
  - Tests → `agent/tests/`
  - Documentation → `project_context/`

### Important Notes
⚠️ **Large Files**: Do not commit Unity builds or large binaries. Keep system files local only.

📖 **Detailed Setup**: See `DEVELOPMENT.md` for complete setup instructions and VS Code configuration.

