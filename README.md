# Agent-in-the-Loop Repository

*An intelligent real-time strategy game analysis system combining computer vision, AI decision-making, and interactive visualization.*

## System Overview

This project implements a complete Agent-in-the-Loop system that captures, analyzes, and provides strategic advice for real-time strategy games. The system consists of three integrated components working together to create an intelligent game analysis pipeline.

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Screen Reading │───▶│ Decision Logic   │───▶│  Visualization  │
│                 │    │                  │    │                 │
│ • OCR Engine    │    │ • LangGraph AI   │    │ • GUI Overlay   │
│ • ROI Capture   │    │ • Strategy Analysis│   │ • User Control  │
│ • Image Processing    │ • Game State Logic    │ • Real-time Display │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## System Architecture

### Screen Reading System (`agent/screen_reading/`)
**Purpose**: Computer vision and OCR for real-time game data extraction

**Key Features**:
- **ROI Studio**: Interactive calibration tool for setting up text recognition regions
- **Game Reader**: Automated system that reads game data using calibrated settings
- **Multi-engine OCR**: PaddleOCR (primary) and Tesseract (backup) support
- **Advanced preprocessing**: 5 different image enhancement methods
- **Pattern validation**: Smart text validation using custom patterns
- **Auto-scaling**: Automatic text size optimisation for OCR accuracy
- **Resolution-adaptive**: Automatic ROI selection for 2560x1440 and 1920x1080 displays
- **Multi-monitor support**: Automatic monitor detection and coordinate translation
- **Batch processing**: Bulk capture then batch OCR (user freed after ~15s)
- **Real-time stats**: Live simulation statistics (faction totals, base control, actions)

**Entry Points**:
- `LIVE_ROI_STUDIO.py` - Interactive calibration and setup tool
- `LIVE_GAME_READER.py` - Automated game reading system

### Decision Logic System (`agent/decision_logic/`)
**Purpose**: AI-powered strategic analysis using LangGraph and OpenAI

**Key Features**:
- **LangGraph workflow**: Multi-phase decision-making pipeline
- **Strategy analysis**: Evaluates game state and provides strategic advice
- **Two modes**: Simple advice or detailed multi-phase analysis
- **State management**: Comprehensive game state tracking and validation
- **JSON integration**: Processes game state data from screen reading system

**Workflow Phases**:
1. **Prepare & Select**: Load game state and select analysis mode
2. **Summary**: Generate game situation overview
2b. **Simple Advice**: Single-call strategic evaluation
3. **Phase Analysis**: Multi-step strategic evaluation
4. **Rationale**: Decision reasoning and logic
5. **Finalize**: Output generation and formatting

### Visualization System (`agent/visualisation/`)
**Purpose**: Interactive GUI overlay for user control and real-time display

**Key Features**:
- **External overlay**: Hooks onto RTSViewer game window
- **Integrated pipeline**: Single-button execution of full analysis workflow
- **Real-time control**: Interactive buttons for all system operations
- **Progress tracking**: Live updates during screen reading and analysis
- **Process management**: Aggressive termination for instant cancellation
- **Output display**: Shows AI recommendations in chatbox overlay
- **Session management**: Automatic bridging between components

**Components**:
- `main.py` - Application entry point
- `ui.py` - Interface layout and functionality
- `external_overlay/` - Window management and game integration

## System Requirements

### Minimum (CPU-only)
- Dual-core CPU (2+ GHz)
- 4GB RAM
- Windows 10/11 (64-bit)
- 1920×1080 or 2560×1440 display
- Python 3.9+

### Recommended (GPU-accelerated)
- Quad-core CPU (3+ GHz)
- 8GB RAM
- NVIDIA GPU with 2GB+ VRAM (CUDA 11.8)
- Windows 10/11 (64-bit)
- Python 3.11

### Performance Tuning

**GPU Memory** (for GPUs with <2GB VRAM):
```bash
# PowerShell
$env:PADDLE_GPU_MEMORY_FRACTION="0.3"

# Command Prompt
set PADDLE_GPU_MEMORY_FRACTION=0.3
```
Default: 50%. Low-end GPUs: 30%. High-end GPUs: 80%.

**OCR Speed** (for older CPUs):
```bash
# PowerShell
$env:OCR_MAX_SCALES="3"

# Command Prompt
set OCR_MAX_SCALES=3
```
Default: 5 scales (accurate). Low-end: 3 scales (40% faster).

Set environment variables before running Python scripts.

### Resource Usage
- **Memory**: 68-118 MB image processing + 500 MB PaddleOCR models
- **CPU/GPU**: 4 parallel workers, 50-100% utilization during OCR
- **Disk**: 50-100 MB per session (auto-cleanup keeps 10 most recent)

## Quick Start

### Prerequisites

- **Python 3.9+** (developed with Python 3.11)
- **RTSViewer game** (included in `system_files/`)
- **4GB+ RAM**
- **Windows OS** (for PyWin32 overlay functionality)

**Optional**:
- **NVIDIA GPU** with CUDA 11.8 for faster OCR (2GB+ VRAM recommended)
- **Tesseract OCR** for backup text recognition (see installation guide below)

### Installation

1. **Clone and navigate to repository**:
```bash
git clone <repository-url>
cd Agent-in-the-Loop-Repository
```

2. **Create virtual environment**:
```bash
python -m venv venv

# Windows PowerShell
venv\Scripts\Activate.ps1

# Windows Command Prompt
venv\Scripts\activate.bat

3. **Install dependencies**:
```bash
pip install --upgrade pip || python.exe -m pip install --upgrade pip
pip install -r requirements.txt
```

4. **Configure environment** (create `.env` file):
```env
OPENAI_API_KEY=your_openai_api_key_here
MODEL_NAME=gpt-4o-mini
PROMPTS_DIR=./prompts
STRATEGIES_DIR=./strategies
GAME_STATE_PATH=./game_state
```

5. **Install Tesseract OCR**:

Tesseract provides an additional OCR engine for improved text recognition accuracy as a fallback to PaddleOCR.

**Windows Installation**:

a. Download the Tesseract installer:
   - Visit: https://github.com/UB-Mannheim/tesseract/wiki
   - Download the latest Windows installer (e.g., `tesseract-ocr-w64-setup-5.3.x.exe`)

b. Run the installer:
   - **Important**: During installation, note the installation path (default: `C:\Program Files\Tesseract-OCR`)
   - Ensure "Add to PATH" is selected during installation, OR manually add it after installation

c. Add Tesseract to system PATH (if not added automatically):
   - Open System Properties → Environment Variables
   - Under "System Variables", find and edit "Path"
   - Add new entry: `C:\Program Files\Tesseract-OCR` (or your installation path)

d. Verify installation:
```bash
tesseract --version
```
You should see version information if installed correctly.

e. Configure pytesseract path (if needed):
If Tesseract is not found automatically, you may need to set the path in your Python code or create a `tessdata` environment variable pointing to `C:\Program Files\Tesseract-OCR\tessdata`

### Usage Workflow

**Important**: Launch RTSViewer manually first, then run the system.

#### Option 1: Integrated System Launch (Recommended)

**One-click system startup**:
```bash
# From repository root
start_system.bat
```
This launches the visualization overlay system. **Prerequisite**: RTSViewer must be running before executing this command.

#### Option 2: Manual Component Launch

1. **Start RTSViewer Game**:
```bash
cd system_files
./RTSViewer.exe
```

2. **Calibrate Screen Reading** (first-time setup):
```bash
cd agent/screen_reading
python LIVE_ROI_STUDIO.py
```
- Draw regions of interest (ROIs) on game interface
- Test OCR accuracy with different preprocessing methods
- Define text validation patterns
- Save template for automated reading

**Important Notes on ROI Calibration**:
- **Pre-calibrated templates** are included for **2560x1440** and **1920x1080** resolutions
- System **automatically detects** your monitor resolution and loads the appropriate ROI file
- **Fallback templates** (`_custom.json` files) used for unknown resolutions
- **Multi-monitor support**: Automatically detects which monitor RTSViewer is on and adjusts coordinates
- If auto-detection doesn't work for your setup, use the ROI Studio calibrator to create custom templates
- Each template contains position coordinates, preprocessing settings, and validation patterns optimised for accurate OCR

3. **Run Automated Game Reading**:
```bash
cd agent/screen_reading
python LIVE_GAME_READER.py
```
- Auto-detects monitor resolution and loads appropriate ROI templates
- Detects RTSViewer window location across multiple monitors
- Performs batch capture (~15s mouse lock) then batch OCR processing (user freed)
- Smart popup system: detects save_state.json or prompts for phase selection
- Exports game state as JSON for AI analysis
- Generates real-time stats.txt with simulation statistics

4. **Launch Integrated System (AI Analysis & Visualization)**:
```bash
cd agent/visualisation
python main.py
```
- Overlay GUI appears on game window with control buttons:
  - **Generate Strategy**: Runs full pipeline (screen reading → AI analysis)
  - **Cancel**: Stops current operations immediately
  - **Launch ROI Studio**: Opens calibration tool
  - **Exit System**: Graceful shutdown of all components
- If Generate Strategy is run with a save_state from the game the detailed pathway is run
- If Generate Strategy is run without a save_state the simple pathway is activated
- Progress tracking shows real-time status during processing
- View strategic recommendations in chatbox overlay
- Processing time: ~2-2.5 minutes (optimized from 5 minutes)

## ROI Templates and Calibration

### Understanding ROI Templates

The system uses **Region of Interest (ROI) templates** to identify and extract text from specific areas of the game interface. These templates are stored in the `rois/main/` directory and contain:

- **Coordinate positions** for each text region
- **Preprocessing method** optimized for that specific region
- **Text validation patterns** to ensure accurate recognition
- **Auto-scaling settings** for optimal OCR performance

### How LIVE_GAME_READER Uses Templates

The `LIVE_GAME_READER.py` script:
1. Auto-detects monitor resolution and RTSViewer window location
2. Loads resolution-specific ROI templates (or _custom fallback)
3. **Smart capture planning**: Detects save_state.json or prompts user for phase selection
4. **Bulk capture phase (~15s)**: Captures all screenshots with mouse lock
5. **Batch OCR phase (~2min)**: User freed, parallel processing of all captures
6. Applies calibrated preprocessing and validates against patterns
7. Generates game_state.json AND real-time stats.txt with simulation data

### Resolution and Multi-Monitor Support

**Automatic Resolution Detection**:
- System auto-detects monitor resolution (2560x1440 or 1920x1080)
- Loads resolution-specific ROI templates automatically
- Falls back to `_custom.json` templates for unknown resolutions

**Multi-Monitor Support**:
- Automatically detects which monitor RTSViewer is displayed on
- Translates ROI coordinates using global monitor offsets
- Navigation (button clicks) works correctly across all monitor setups

**If auto-detection doesn't work for your setup**:
- Run `python LIVE_ROI_STUDIO.py` to create custom templates for your resolution
- Save templates with `_custom.json` suffix to be used as fallback

### Calibration Best Practices

When calibrating ROIs for your display:
1. Ensure RTSViewer is running at your native resolution
2. Draw ROI boxes tightly around text regions to minimize noise
3. Test multiple preprocessing methods to find the most accurate one
4. Define validation patterns to catch OCR errors
5. Use the auto-scaling feature if text appears too small or large
6. Save templates with descriptive names for easy identification

### Cross-Game Use

**Setting Up the Agentic Framework for Other RTS Games**

The agent's simple pathway is designed to be game-agnostic - you can adapt it to analyse and advise for any RTS title by editing the three prompt files in /prompts.

- Simple_Reading.md
  Adjust the expected JSON structure here to match your chosen game’s regions of interest (ROIs) and OCR calibration. Each “base” or “zone” should correspond to a measurable area in your                     new game’s UI.

- Simple_Advice.md
  Redefine what lock, insert, and delete mean within the context of your game. For example, lock could mean “continue this tactic,” delete could mean “avoid this move,” and insert could  mean “add or consider this action.” The JSON output schema must remain unchanged to preserve compatibility.

- Simple_System.md
  Use this file to describe the core rules of your game - unit types, movement logic, and win conditions. This gives the agent grounding for interpreting the data and generating meaningful advice.

Keep edits minimal and structured. As long as the JSON format and file roles are preserved, the agent will automatically adapt to new RTS environments. When ready use simple pathway to test results.

## Component Dependencies

### Screen Reading
- **Computer Vision**: PaddleOCR, OpenCV, Pillow, NumPy
- **Screen Capture**: MSS (Multi-Screen Screenshot)
- **Automation**: PyAutoGUI
- **Alternative OCR**: PyTesseract

### Decision Logic
- **AI Framework**: LangGraph, LangChain
- **Language Models**: OpenAI GPT integration
- **Data Validation**: Pydantic
- **Configuration**: python-dotenv

### Visualization
- **GUI Framework**: DearPyGui
- **System Integration**: PyWin32 (Windows overlay)
- **Process Management**: PSUtil

## Project Structure

```
Agent-in-the-Loop-Repository/
├── agent/
│   ├── screen_reading/          # Computer vision & OCR system
│   │   ├── LIVE_ROI_STUDIO.py   # Interactive calibration tool
│   │   ├── LIVE_GAME_READER.py  # Automated reading system
│   │   ├── roi_studio/          # GUI components for setup
│   │   ├── game_reader/         # Automation engine
│   │   ├── core/                # Data models and validation
│   │   ├── ocr/                 # OCR processing pipeline
│   │   ├── imaging/             # Computer vision utilities
│   │   ├── rois/                # ROI templates and configurations
│   │   └── requirements.txt
│   ├── decision_logic/          # AI analysis system
│   │   └── run_agent/
│   │       ├── run_agent.py     # Main agent entry point
│   │       ├── graph/           # LangGraph workflow definition
│   │       ├── nodes/           # Analysis pipeline nodes
│   │       ├── helpers/         # Utility functions
│   │       ├── validators/      # Data validation logic
│   │       └── prompts/	 # Calibrated prompts for agent
│   └── visualisation/           # GUI overlay system
│       ├── main.py              # Application entry point
│       ├── ui.py                # Interface components
│       ├── external_overlay/    # Window management
│       ├── agent_bridge.py      # Integration between components
│       ├── win_termination.py   # Process management utilities
│       └── finalOutput.txt      # AI analysis results
├── system_files/                # RTSViewer game files
├── project_context/             # Documentation and references
├── requirements.txt             # Combined dependencies
├── start_system.bat             # One-click system launcher
└── README.md                    # This file
```

## Development Notes

**Code Standards**:
- **Python 3.9+** compatibility
- **Modular architecture** with clear component separation
- **Error handling** for robust computer vision processing
- **Logging infrastructure** for debugging and monitoring

**Performance Considerations**:
- **GPU acceleration** available for PaddleOCR
- **Threaded execution** in GUI for responsiveness
- **Efficient screen capture** with MSS library
- **Pattern-based validation** prioritizes accuracy over speed

## Troubleshooting

**Screen Reading Issues**:
- Ensure RTSViewer is running before calibration
- Try different OCR preprocessing methods for poor accuracy
- Use auto-scaling feature for optimal text size
- Run as administrator if screen capture fails
- If processing is slow, verify GPU acceleration is enabled for PaddleOCR
- Check that parallel processing shows "(Parallel)" in phase headers
- For multi-monitor issues, ensure RTSViewer is visible on the detected monitor
- If resolution detection fails, check that ROI files exist for your resolution or use _custom fallback

**AI Analysis Issues**:
- Verify OpenAI API key is configured correctly
- Check that game state JSON files are being generated
- Ensure sufficient memory for language model processing

**Visualization Issues**:
- Confirm PyWin32 is installed for Windows overlay
- Verify RTSViewer window is active and visible
- Check that finalOutput.txt is being updated by AI system

## Academic Context

This project demonstrates practical applications of:
- **Computer Vision** in real-time game analysis
- **Agent-based AI systems** for strategic decision making
- **Human-AI interaction** through overlay interfaces
- **Multi-component system integration** with clear data pipelines

**Author**: Agent in the Loop - Group 2 
**Institution**: Edith Cowan University - Computer Science
**Project Type**: Agent-in-the-Loop Implementation for final Applied Project