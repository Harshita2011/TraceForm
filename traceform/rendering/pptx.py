"""
# §3.3 / §6 Presentation Renderer — converts slide JSON to .pptx via python-pptx.

Input schema (as produced by the 'presentation' generator YAML config):
  [
    {
      "title": "Slide Title",
      "bullets": ["Bullet 1", "Bullet 2"],
      "speaker_notes": "Optional speaker notes text"   # optional
    },
    ...
  ]

The first element is treated as the title slide (title + subtitle from bullets[0] if present).
Subsequent slides are content slides (title + bullet list).

Returns raw .pptx bytes, ready for storage.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

logger = logging.getLogger(__name__)

# ── Colour palette ──────────────────────────────────────────────────────────
_BG_COLOR = RGBColor(0x0F, 0x17, 0x2A)       # deep navy background
_ACCENT_COLOR = RGBColor(0x5B, 0x8D, 0xEA)   # bright blue accent
_TITLE_COLOR = RGBColor(0xFF, 0xFF, 0xFF)     # white title text
_BODY_COLOR = RGBColor(0xD0, 0xD8, 0xF0)     # light lavender body text

# ── Layout constants ────────────────────────────────────────────────────────
_SLIDE_WIDTH = Inches(13.33)
_SLIDE_HEIGHT = Inches(7.5)
_MARGIN = Inches(0.6)

# Title slide layout indices in the blank template
_BLANK_LAYOUT = 6   # "Blank" layout — we control all boxes ourselves


def render_presentation(content: str | list[dict] | dict) -> bytes:
    """
    Render a .pptx from slide JSON produced by the presentation generator.

    Args:
        content: Either a JSON string, a list of slide dicts, or a dict with a
                 'slides' key. Both forms the generator may return are handled.

    Returns:
        Raw .pptx bytes.

    Raises:
        ValueError: If content cannot be parsed or has no slides.
    """
    slides_data = _parse_content(content)
    if not slides_data:
        raise ValueError("Presentation content has no slides to render.")

    prs = Presentation()
    prs.slide_width = _SLIDE_WIDTH
    prs.slide_height = _SLIDE_HEIGHT

    blank_layout = prs.slide_layouts[_BLANK_LAYOUT]

    for idx, slide_data in enumerate(slides_data):
        slide = prs.slides.add_slide(blank_layout)
        _set_slide_background(slide, _BG_COLOR)

        title_text = slide_data.get("title", f"Slide {idx + 1}")
        bullets: list[str] = slide_data.get("bullets", [])
        speaker_notes: str = slide_data.get("speaker_notes", "")

        if idx == 0:
            # Title slide — large centred title + optional subtitle
            _add_title_slide_content(slide, title_text, bullets)
        else:
            # Content slide — title bar + bulleted body
            _add_content_slide_content(slide, title_text, bullets)

        if speaker_notes:
            _set_speaker_notes(slide, speaker_notes)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ── Content builders ─────────────────────────────────────────────────────────

def _add_title_slide_content(slide, title: str, bullets: list[str]) -> None:
    """Title slide: large centred title + subtitle (first bullet) below."""
    # Title box
    title_box = slide.shapes.add_textbox(
        _MARGIN, Inches(2.2),
        _SLIDE_WIDTH - 2 * _MARGIN, Inches(2.0),
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = title
    run.font.color.rgb = _TITLE_COLOR
    run.font.size = Pt(44)
    run.font.bold = True

    # Accent rule
    slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        _MARGIN, Inches(4.3), _SLIDE_WIDTH - 2 * _MARGIN, Pt(3),
    ).fill.fore_color.rgb = _ACCENT_COLOR

    # Subtitle (first bullet or empty)
    subtitle = bullets[0] if bullets else ""
    if subtitle:
        sub_box = slide.shapes.add_textbox(
            _MARGIN, Inches(4.5),
            _SLIDE_WIDTH - 2 * _MARGIN, Inches(1.2),
        )
        tf2 = sub_box.text_frame
        p2 = tf2.paragraphs[0]
        p2.alignment = PP_ALIGN.CENTER
        run2 = p2.add_run()
        run2.text = subtitle
        run2.font.color.rgb = _BODY_COLOR
        run2.font.size = Pt(22)


def _add_content_slide_content(slide, title: str, bullets: list[str]) -> None:
    """Content slide: top title bar + bulleted list below."""
    # Title background bar
    title_bar = slide.shapes.add_shape(
        1,  # RECTANGLE
        0, 0, _SLIDE_WIDTH, Inches(1.1),
    )
    title_bar.fill.fore_color.rgb = _ACCENT_COLOR
    title_bar.line.fill.background()

    # Title text
    title_box = slide.shapes.add_textbox(
        _MARGIN, Inches(0.1),
        _SLIDE_WIDTH - 2 * _MARGIN, Inches(0.9),
    )
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = title
    run.font.color.rgb = _TITLE_COLOR
    run.font.size = Pt(28)
    run.font.bold = True

    # Bullet body
    if bullets:
        body_box = slide.shapes.add_textbox(
            _MARGIN, Inches(1.3),
            _SLIDE_WIDTH - 2 * _MARGIN, Inches(5.8),
        )
        tf2 = body_box.text_frame
        tf2.word_wrap = True
        for i, bullet in enumerate(bullets):
            para = tf2.paragraphs[0] if i == 0 else tf2.add_paragraph()
            para.level = 0
            run = para.add_run()
            run.text = f"• {bullet}"
            run.font.color.rgb = _BODY_COLOR
            run.font.size = Pt(20)
            para.space_before = Pt(8)


def _set_slide_background(slide, color: RGBColor) -> None:
    """Fill slide background with a solid colour."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _set_speaker_notes(slide, notes_text: str) -> None:
    """Write speaker notes to the slide notes placeholder."""
    notes_slide = slide.notes_slide
    tf = notes_slide.notes_text_frame
    tf.text = notes_text


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _parse_content(content: Any) -> list[dict]:
    """
    Normalise generator output into a list of slide dicts.

    Handles:
    - JSON string → parse → list or dict with 'slides' key
    - Already a list of dicts
    - Dict with a 'slides' key
    """
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Presentation content is not valid JSON: {exc}") from exc

    if isinstance(content, list):
        return content

    if isinstance(content, dict):
        # Generator might return {"slides": [...]} or a bare slide dict
        if "slides" in content:
            return content["slides"]
        # Single slide wrapped in a dict
        if "title" in content:
            return [content]

    raise ValueError(
        f"Presentation content must be a list of slide dicts or a JSON string. Got: {type(content)}"
    )
