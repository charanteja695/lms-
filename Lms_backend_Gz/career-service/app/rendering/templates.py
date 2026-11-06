"""Resume templates. Every one is single-column, text-only (no tables, images or text boxes — the things that scramble an
applicant tracking system's reading order) and uses the standard section headings. They differ only in typography and spacing.
``ats_safe`` is a property of the template's structure: a future template that breaks these rules must set it false, and the
ATS score then says so.
"""

from typing import Any

DEFAULT_TEMPLATES: dict[str, dict[str, Any]] = {
    "classic": {
        "name": "Classic",
        "description": "Serif, centred name, ruled section headings. The safe default for most roles.",
        "config": {"font": "Times-Roman", "bold": "Times-Bold", "italic": "Times-Italic", "size": 10.5, "name_size": 20, "heading_size": 11.5, "align": "center", "rule": True, "accent": "#000000", "leading": 1.25, "space": 7},
    },
    "modern": {
        "name": "Modern",
        "description": "Sans-serif, left-aligned name, a single accent colour on headings.",
        "config": {"font": "Helvetica", "bold": "Helvetica-Bold", "italic": "Helvetica-Oblique", "size": 10, "name_size": 22, "heading_size": 11, "align": "left", "rule": False, "accent": "#1f4e79", "leading": 1.3, "space": 8},
    },
    "compact": {
        "name": "Compact",
        "description": "Tighter spacing to keep a longer resume on one page.",
        "config": {"font": "Helvetica", "bold": "Helvetica-Bold", "italic": "Helvetica-Oblique", "size": 9, "name_size": 17, "heading_size": 10, "align": "left", "rule": True, "accent": "#000000", "leading": 1.2, "space": 4},
    },
}
DEFAULT_TEMPLATE_KEY = "classic"
