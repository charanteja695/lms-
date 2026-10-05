"""Server-rendered PDF (docs/PRODUCT.md §5.6: "server-rendered, consistent"): the same document and template always produce the
same layout, whatever the reader's browser. Built with reportlab's standard fonts, so the text stays real, selectable text that an
applicant tracking system can read.

Limit: the standard fonts cover Latin (Western European) characters only. Any other character (Devanagari, for instance) is
replaced with ``?`` and counted, so the caller can warn the student; the JSON Resume export and the share page keep Unicode.
"""

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer


def _latin(text: str, counter: list[int]) -> str:
    """cp1252 is what the PDF standard fonts encode (it keeps en/em dashes, curly quotes and the bullet)."""
    out = []
    for ch in text:
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            counter[0] += 1
            out.append("?")
    return "".join(out)


def render_pdf(document: dict[str, Any], config: dict[str, Any], *, title: str) -> tuple[bytes, int]:
    """Returns ``(pdf bytes, number of characters that could not be drawn)``."""
    lost = [0]

    def t(value: str | None) -> str:
        return escape(_latin(value or "", lost))

    size, leading = float(config["size"]), float(config["leading"])
    align = TA_CENTER if config.get("align") == "center" else TA_LEFT
    accent = HexColor(config.get("accent", "#000000"))
    body = ParagraphStyle("body", fontName=config["font"], fontSize=size, leading=size * leading, alignment=TA_LEFT)
    name = ParagraphStyle("name", parent=body, fontName=config["bold"], fontSize=config["name_size"], leading=config["name_size"] * 1.15, alignment=align)
    contact = ParagraphStyle("contact", parent=body, alignment=align, fontSize=size - 0.5)
    heading = ParagraphStyle("heading", parent=body, fontName=config["bold"], fontSize=config["heading_size"], leading=config["heading_size"] * 1.2, textColor=accent, spaceBefore=config["space"], spaceAfter=2)
    entry_head = ParagraphStyle("entry", parent=body, fontName=config["bold"], spaceBefore=3)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=11, bulletIndent=1, spaceBefore=0.5)

    story: list[Any] = []
    personal = document["personal"]
    story.append(Paragraph(t(personal["name"]), name))
    if personal.get("headline"):
        story.append(Paragraph(t(personal["headline"]), contact))
    bits = [b for b in (personal.get("email"), personal.get("phone"), personal.get("location"), *[link["url"] for link in personal.get("links", [])]) if b]
    if bits:
        story.append(Paragraph(t("  |  ".join(bits)), contact))
    if document.get("summary"):
        story.append(_section_heading("Summary", heading, config, accent))
        story.append(Paragraph(t(document["summary"]), body))
    for section in document["sections"]:
        block: list[Any] = [_section_heading(section["title"], heading, config, accent)]
        if section["key"] == "skills":  # skills read best as one line, the way most parsers expect them
            story.extend([*block, Paragraph(t(", ".join(e["heading"] for e in section["entries"])), body)])
            continue
        story.extend(block)
        for entry in section["entries"]:
            title_line = entry["heading"] + (f" — {entry['subheading']}" if entry.get("subheading") and section["key"] in {"experience", "education", "projects"} else "")
            right = "  ·  ".join(x for x in (entry.get("dates"), entry.get("location")) if x)
            parts = [Paragraph(t(title_line) + (f"  <font name='{config['font']}' size='{size - 0.5}'>({t(right)})</font>" if right else ""), entry_head)]
            parts += [Paragraph(t(b), bullet, bulletText="•") for b in entry["bullets"]]
            story.append(KeepTogether(parts))
        story.append(Spacer(1, 1))
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title=_latin(title, [0]), author=_latin(personal["name"], [0]), creator="LMS career-service",
    )
    doc.build(story)
    return buffer.getvalue(), lost[0]


def _section_heading(title: str, style: ParagraphStyle, config: dict[str, Any], accent: Any) -> Any:
    heading = Paragraph(escape(_latin(title.upper(), [0])), style)
    if config.get("rule"):
        return KeepTogether([heading, HRFlowable(width="100%", thickness=0.6, color=accent, spaceAfter=2)])
    return heading
