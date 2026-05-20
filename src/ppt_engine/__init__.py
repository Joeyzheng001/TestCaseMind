"""
ThesisMind PPT Engine — SVG-to-PPTX generation for thesis defense.

Integrates ppt-master's native DrawingML pipeline:
  1. SVG post-processing (icon embedding, image alignment, text flattening)
  2. SVG-to-PPTX conversion (native editable shapes, not embedded images)

Public API:
    - generate_pptx(): Main entry point — SVG files → PPTX
    - finalize_svgs(): Post-process SVG files before conversion
    - list_defense_templates(): List available thesis defense templates
"""

from .config import OUTPUT_DIR, TEMPLATES_DIR, DEFAULT_FORMAT, DEFENSE_TEMPLATES

__all__ = [
    'generate_pptx',
    'finalize_svgs',
    'list_defense_templates',
    'OUTPUT_DIR',
    'TEMPLATES_DIR',
    'DEFAULT_FORMAT',
    'DEFENSE_TEMPLATES',
]


def finalize_svgs(svg_dir, output_dir=None, steps=None):
    """Post-process SVG files (embed icons, align images, flatten text, fix rounded rects).

    Args:
        svg_dir: Directory containing SVG files to process.
        output_dir: Output directory (defaults to svg_dir + '_final').
        steps: List of steps to run. Default all: ['embed-icons', 'align-images', 'flatten-text', 'fix-rounded']

    Returns:
        Path to the output directory.
    """
    import shutil
    from pathlib import Path
    from .svg_finalize.embed_icons import process_svg_file as _embed_icons_in_file
    from .svg_finalize.align_embed_images import (
        align_and_embed_images_in_svg as _align_images,
    )

    svg_dir = Path(svg_dir)
    if output_dir is None:
        output_dir = svg_dir.parent / (svg_dir.name + '_final')
    else:
        output_dir = Path(output_dir)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(svg_dir, output_dir)

    all_steps = ['embed-icons', 'align-images', 'flatten-text', 'fix-rounded']
    if steps is None:
        steps = all_steps

    svg_files = sorted(output_dir.glob('*.svg'))
    if not svg_files:
        return output_dir

    icons_dir = Path(__file__).parent / 'templates' / 'icons'

    for step in steps:
        for svg_file in svg_files:
            if step == 'embed-icons':
                _embed_icons_in_file(svg_file, icons_dir=icons_dir)
            elif step == 'align-images':
                _align_images(svg_file)

        if step == 'flatten-text':
            try:
                from .svg_finalize.flatten_tspan import flatten_text_with_tspans
                from xml.etree import ElementTree as ET
                for svg_file in svg_files:
                    tree = ET.parse(str(svg_file))
                    if flatten_text_with_tspans(tree):
                        tree.write(str(svg_file), encoding='unicode', xml_declaration=False)
            except Exception:
                pass

        if step == 'fix-rounded':
            try:
                from .svg_finalize.svg_rect_to_path import convert_svg_rounded_rects
                convert_svg_rounded_rects(output_dir, svg_files)
            except Exception:
                pass

    return output_dir


def generate_pptx(svg_dir, output_path=None, format='ppt169', source='final',
                  notes_dir=None, narration_dir=None, transition='fade',
                  animation='fade', animation_trigger='auto', **kwargs):
    """Convert SVG files to a native editable PPTX.

    Args:
        svg_dir: Directory containing SVG slide files (e.g., 'slide_01_cover.svg').
        output_path: Output PPTX path. Auto-generated if None.
        format: Canvas format ('ppt169', 'ppt43', etc.).
        source: SVG source — 'final' for post-processed, 'output' for raw.
        notes_dir: Optional directory with per-slide Markdown notes.
        narration_dir: Optional directory with per-slide audio files.
        transition: Default transition effect ('fade', 'push', 'none', etc.).
        animation: Default entrance animation ('fade', 'fly', 'zoom', 'none', etc.).
        animation_trigger: 'auto' (cascade after transition) or 'on-click'.

    Returns:
        Path to the generated PPTX file.
    """
    from pathlib import Path
    from datetime import datetime

    from .svg_to_pptx.pptx_builder import create_pptx_with_native_svg
    from .svg_to_pptx.pptx_discovery import find_svg_files, find_notes_files
    from .svg_to_pptx.pptx_narration import NARRATION_EXTENSIONS, find_narration_files

    svg_dir = Path(svg_dir)

    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = OUTPUT_DIR / f'defense_{timestamp}.pptx'
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Find SVG files
    svg_files, svg_dir_name = find_svg_files(svg_dir, source)

    if not svg_files:
        # Try direct glob
        svg_files = sorted(svg_dir.glob('*.svg'))
        if not svg_files:
            raise FileNotFoundError(f"No SVG files found in {svg_dir}")

    # Find notes
    notes = {}
    if notes_dir:
        notes = find_notes_files(Path(notes_dir), svg_files)
    else:
        notes = find_notes_files(svg_dir, svg_files)

    # Find narration
    narration = {}
    if narration_dir:
        narration = find_narration_files(Path(narration_dir), svg_files)

    # Build PPTX
    success = create_pptx_with_native_svg(
        svg_files=svg_files,
        output_path=output_path,
        canvas_format=format,
        notes=notes,
        narration_audio=narration if narration else None,
        transition=transition,
        animation=animation,
        animation_trigger=animation_trigger,
        verbose=False,
        **kwargs,
    )

    if not success:
        raise RuntimeError(f"PPTX generation failed for {output_path}")

    return output_path


def list_defense_templates():
    """List available thesis defense layout templates.

    Returns:
        Dict mapping template names to their paths.
    """
    available = {}
    for name, path in DEFENSE_TEMPLATES.items():
        if path.exists():
            available[name] = str(path)
    return available
