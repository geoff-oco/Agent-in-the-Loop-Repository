# Live ROI Tool - Computer Vision Game Reader

*A modular OCR and computer vision tool for real-time strategy gamestate reading and automation.*

It's designed to read text from games in real-time using advanced OCR (Optical Character Recognition) and computer vision techniques. The tool has two main parts:

Alot of inspiration from - https://github.com/royshil/scoresight a tool used for live OBS extraction and display during games, streaming and video capture.

1. **ROI Studio** - Interactive calibration tool for setting up text recognition regions
2. **Game Reader** - Automated system that reads game data using your calibrated settings

Think of it like creating custom parameters for your computer to understand how to decipher what's happening on-screen!

## Quick Start Guide

### Prerequisites & Special Requirements

Before we start, you'll need:

- **Python 3.9+** (I used 3.11 for development)
- **At least 2GB RAM** (PaddleOCR models are pretty heavy)
- **Tesseract OCR** (optional backup engine)
  - Windows: Download from [GitHub releases](https://github.com/UB-Mannheim/tesseract/wiki)
  - Add to PATH or the tool will find it automatically
- **GPU Support** (optional but faster)
  - NVIDIA GPU with CUDA for PaddleOCR acceleration
  - AMD GPUs work with CPU mode (still fast enough)

### Step-by-Step Setup

**1. Clone and Navigate**
```bash
git clone <Agent-In-The-Loop-Repository">
cd agent/screen_reading
```

**2. Create Virtual Environment**
```bash
# Create the virtual environment
python -m venv .venv

# Activate it (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Or for Command Prompt
.venv\Scripts\activate.bat
```

**3. Install Dependencies**
```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt
```

**4. Test the Installation**
```bash
# Test the ROI Studio (interactive tool)
python LIVE_ROI_STUDIO.py

# Test the Game Reader (automation tool)
python LIVE_GAME_READER.py
```

If you see a GUI window pop up for the studio or game reader output, you're good to go!

## What's Where - Project Structure

Here's how I organised the codebase using modern modular architecture:

```
live_roi_tool/
├── roi_studio/              # Interactive ROI calibration tool
│   ├── studio.py           # Main studio orchestrator (427 lines)
│   ├── ui_components.py    # Shared UI helpers and config
│   ├── capture_manager.py  # Screen capture and display logic
│   ├── template_manager.py # ROI template saving/loading
│   ├── mask_editor.py      # Custom mask creation tools
│   └── ocr_tester.py       # Live OCR testing and preview
├── game_reader/             # Automated game reading system
│   ├── game_reader.py      # Main automation engine
│   ├── session_manager.py  # Output logging and session tracking
│   └── navigation.py       # Template-based game navigation
├── core/                    # Data models and logic
│   ├── roi_manager.py      # ROI data structures and validation
│   └── validation.py       # Pattern matching and text validation
├── ocr/                     # OCR processing pipeline
│   ├── processor.py        # Multi-engine OCR with preprocessing
│   └── engines/            # PaddleOCR and Tesseract implementations
├── imaging/                 # Computer vision utilities
│   ├── screen_capture.py   # Multi-monitor screen capture
│   ├── image_processing.py # Image enhancement and preprocessing
│   └── colour_detection.py # Colour-based validation
├── LIVE_ROI_STUDIO.py      # Entry point for interactive tool
├── LIVE_GAME_READER.py     # Entry point for automation
└── requirements.txt         # All dependencies
```

## The Two Main Tools Explained

### 1. ROI Studio (LIVE_ROI_STUDIO.py)

This is your **calibration and setup tool**. It's like a sophisticated image editor specifically designed for OCR:

**What it does:**
- Captures your screen in real-time
- Lets you draw rectangular regions (ROIs) where text appears
- Tests different OCR methods to find what works best
- Validates text against patterns you define
- Exports everything as a template for automation

**Key Features I'm Proud Of:**
- **5 OCR preprocessing methods** - Original, Enhanced, Binary, Grey-boost, Inverted
- **Smart Auto-Select** - Picks the best method based on pattern matching, not just confidence
- **Auto-scaling** - Automatically finds the best text size for OCR (32-48px is the sweet spot)
- **Pattern validation** - Define formats like `L:(number)H:(number)` to validate extracted text
- **Live preview** - See OCR results update in real-time as you adjust settings

### 2. Game Reader (LIVE_GAME_READER.py)

This is your **automation engine**. It uses the templates you created in the studio:

**What it does:**
- Loads your calibrated ROI templates
- Performs 3-phase automated game reading:
  1. **Navigate** - Click to specific game locations
  2. **Read** - Extract text from predefined regions
  3. **Capture** - Take final measurements over time
- Validates everything against your patterns
- Logs comprehensive session data

**The 3-Phase System:**
- **Phase 1**: Navigate to "red1 base" location automatically
- **Phase 2**: Read initial unit counts and validate them
- **Phase 3**: Navigate to "red2" and sample final unit counts over 5 seconds

## Special Technical Features

### GPU vs CPU for PaddleOCR

**CPU Mode (Default):**
- Works on any machine
- Good enough for real-time OCR (usually <200ms per region)
- Uses `paddlepaddle` package

**GPU Mode (Optional):**
- Much faster (typically <50ms per region)
- Requires NVIDIA GPU with CUDA
- Uncomment `paddlepaddle-gpu>=2.6` in requirements.txt
- Remove the regular `paddlepaddle` line

### Tesseract Integration

The tool includes Tesseract as a backup OCR engine:
- Automatically detected if installed
- Used for comparison and fallback
- Generally less accurate than PaddleOCR for game text
- Good for traditional document text

### Pattern Validation System

One of the coolest features - you can define text patterns that must match:

```python
# Examples of patterns I use:
"L:(number)H:(number)R:(number)"  # Matches: L:45H:23R:12
"(number)/(number)"               # Matches: 850/1000
"Level (number), Lvl (number)"    # Matches: Level 5 OR Lvl 5
```

The system prioritises pattern matches over raw OCR confidence - a 85% confidence result that matches your pattern beats a 100% confidence result that doesn't!

## Development Notes
**Code Standards:**
- **Black formatting** with 120-character lines
- **Type hints** where it helps readability

## Common Issues & Solutions

**1. "PaddleOCR not loading properly"**
- Make sure you have enough RAM (2GB+)
- Try CPU mode first before GPU mode
- Check that numpy versions are compatible

**2. "Screen capture not working"**
- Run as administrator on Windows
- Check that MSS library can access your display
- Try different monitor indices

**3. "OCR accuracy is poor"**
- Use the auto-scaling feature (target 32-48px text height)
- Try different preprocessing methods
- Ensure good contrast between text and background
- Consider creating custom masks for better isolation

**4. "Templates not loading"**
- Check file paths are absolute, not relative
- Ensure JSON structure is valid
- Verify ROI names match between studio and reader

## Learning Outcomes

Building this project taught me:
- **Computer Vision**: Real-world image processing and OCR challenges
- **GUI Development**: Complex Tkinter applications with proper architecture
- **Performance Optimisation**: Making real-time processing smooth and responsive
- **Modular Architecture**: How to structure large Python projects maintainably
- **API Design**: Creating clean interfaces between components
- **Error Handling**: Robust error handling for computer vision edge cases
- **Extreme Patience**: OCR and Computer Vision is like trial and error to the max (this was painstaking at times)

**Author**: Brody Orchard (Student ID: 10582880)
**Course**: Computer Science - Software Engineering @ECU
