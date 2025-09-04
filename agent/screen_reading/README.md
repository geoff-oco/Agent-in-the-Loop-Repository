# Screen Reading System

RTS game screen reading using OCR and template matching.

## Setup

**Prerequisites**: Python 3.8+, Tesseract OCR

```powershell
# Navigate to project root
cd "Agent in The Loop Repository"

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Navigate to screen reading module
cd agent\screen_reading

# Run system
python main.py
```

## Usage

```powershell
python main.py              # Basic run
python main.py --debug      # Debug mode
python main.py --info       # System info
```

## Configuration

### ROI Setup

**ROI definitions**: `config/rois.json` contains 23 pre-configured regions of interest using relative coordinates (0.0-1.0). These have been optimized for the RTSViewer window and should work out of the box.

**ROI coordinates are relative** - meaning they scale automatically with different window sizes. The current configuration is optimized and should not need adjustment unless the game interface changes.

If ROI recalibration is needed:
```powershell
python config/rois/roi_calibrator.py  # Interactive ROI setup tool
```

**Templates**: `config/templates/` (PNG files for action card detection)

## Output

- `game_state.json` - Extracted game data
- `debug_rois.json` - Detailed results  
- `roi_captures/` - Debug images

## Components

### Core Scripts

- **main.py** - Entry point and CLI interface
- **orchestrator.py** - Main system coordinator, manages the full analysis pipeline
- **game_state_builder.py** - Combines extracted data into structured game state

### Screen Capture (`capture/`)

- **screen_capture.py** - Captures game window or monitor screenshots
- **window_detector.py** - Finds and identifies the RTSViewer game window

### Processing (`processing/`)

- **ocr_processor.py** - Tesseract OCR text extraction with game-specific parsing
- **roi_manager.py** - Manages regions of interest, crops screen areas
- **image_preprocessor.py** - Image enhancement for better OCR results

### Template Matching (`template_matching/`)

- **template_matcher.py** - OpenCV template matching engine
- **action_card_processor.py** - Detects and extracts action card information

### Configuration & Utilities

- **roi_calibrator.py** - Interactive tool for setting up ROI coordinates
- **debug_utils.py** - Debug image saving and processing time logging
- **file_utils.py** - File operations and JSON handling
- **models/schema.py** - Data structures for game state (LER, Units, etc.)

## Troubleshooting

**Window not found**: Ensure RTSViewer is running
**Poor OCR**: Check ROI definitions, images, exports and Tesseract installation  
**No action cards**: Verify template files exist