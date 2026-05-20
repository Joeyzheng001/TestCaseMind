"""
ThesisMind PPT engine configuration.
Adapted from ppt-master-main for ThesisMind's directory structure.
"""
import os
from pathlib import Path

# Project root (ThesisMind/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Output directory for generated PPTX files
OUTPUT_DIR = PROJECT_ROOT / "output" / "ppt"

# Template directories (bundled with the engine)
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
LAYOUTS_DIR = TEMPLATES_DIR / "layouts"
CHARTS_DIR = TEMPLATES_DIR / "charts"
ICONS_DIR = TEMPLATES_DIR / "icons"

# Knowledge base
KB_DIR = PROJECT_ROOT / "knowledge_base"

# Canvas format definitions
CANVAS_FORMATS = {
    'ppt169': {
        'name': 'PPT 16:9',
        'dimensions': '1280x720',
        'viewbox': '0 0 1280 720',
        'aspect_ratio': '16:9',
    },
    'ppt43': {
        'name': 'PPT 4:3',
        'dimensions': '1024x768',
        'viewbox': '0 0 1024 768',
        'aspect_ratio': '4:3',
    },
    'story': {
        'name': 'Story/Vertical',
        'dimensions': '1080x1920',
        'viewbox': '0 0 1080 1920',
        'aspect_ratio': '9:16',
    },
    'banner': {
        'name': 'Horizontal Banner',
        'dimensions': '1920x1080',
        'viewbox': '0 0 1920 1080',
        'aspect_ratio': '16:9',
    },
}

# Default canvas format for thesis defense (16:9 wide)
DEFAULT_FORMAT = 'ppt169'

# Template presets for thesis defense scenarios
DEFENSE_TEMPLATES = {
    'academic_defense': LAYOUTS_DIR / 'academic_defense',
    'medical_university': LAYOUTS_DIR / 'medical_university',
    'chongqing_university': LAYOUTS_DIR / '重庆大学',
}

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)
