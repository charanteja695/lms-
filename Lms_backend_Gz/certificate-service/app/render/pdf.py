"""Draws a certificate as a PDF (reportlab) with a QR code to its public verification page (segno).

Pure: everything printed comes in through ``CertificateData``, so the same file is produced whether it is rendered for a
real certificate, a template preview, or a regeneration.
"""

import io
import textwrap
from dataclasses import dataclass
from typing import Any

import segno
from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from app.render.layout import fill


@dataclass(frozen=True, slots=True)
class CertificateData:
    certificate_id: str
    student_name: str
    course_title: str
    institution_name: str
    completion_date: str  # already formatted, e.g. "21 September 2026"
    score_percent: str
    grade: str
    issuer: str
    verification_url: str
    verification_code: str
    template: dict[str, Any]

    def values(self) -> dict[str, str]:
        return {
            "student_name": self.student_name,
            "course_title": self.course_title,
            "completion_date": self.completion_date,
            "institution_name": self.institution_name,
            "score_percent": self.score_percent,
            "grade": self.grade,
            "issuer": self.issuer,
            "certificate_id": self.certificate_id,
        }


def _qr(pdf: canvas.Canvas, url: str, x: float, y: float, size: float) -> None:
    matrix = segno.make(url, error="m").matrix
    rows = len(matrix)
    module = size / (rows + 8)  # a 4-module quiet zone on every side
    pdf.setFillColor(black)
    for row_index, row in enumerate(matrix):
        for column_index, dark in enumerate(row):
            if dark:
                pdf.rect(x + (column_index + 4) * module, y + size - (row_index + 5) * module, module, module, stroke=0, fill=1)


def _centered(pdf: canvas.Canvas, text: str, y: float, font: str, size: float, width: float) -> float:
    pdf.setFont(font, size)
    pdf.drawCentredString(width / 2, y, text)
    return y


def render_pdf(data: CertificateData) -> bytes:
    template = data.template
    accent = HexColor(template["accent_color"])
    width, height = landscape(A4)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height), invariant=1)  # invariant: identical bytes for identical input
    pdf.setTitle(f"{template['title_text']} - {data.student_name}")
    pdf.setAuthor(data.issuer)

    pdf.setStrokeColor(accent)
    pdf.setLineWidth(6)
    pdf.rect(24, 24, width - 48, height - 48)
    pdf.setLineWidth(1)
    pdf.rect(34, 34, width - 68, height - 68)

    pdf.setFillColor(accent)
    _centered(pdf, template["title_text"], height - 110, "Helvetica-Bold", 34, width)
    pdf.setFillColor(black)

    y = height - 165
    for line in fill(template["body_text"], data.values()).splitlines():
        line = line.strip()
        if not line:
            continue
        is_name = line == data.student_name or line == data.course_title
        font, size = ("Helvetica-Bold", 26) if is_name else ("Helvetica", 14)
        for part in textwrap.wrap(line, width=70 if not is_name else 45) or [""]:
            _centered(pdf, part, y, font, size, width)
            y -= size + 12
        y -= 4

    _centered(pdf, f"Completed on {data.completion_date}", 150, "Helvetica", 12, width)

    signatories = template.get("signatories") or []
    if signatories:
        slot = (width - 200) / len(signatories)
        for index, signatory in enumerate(signatories):
            x = 100 + slot * index + slot / 2
            pdf.line(x - 70, 110, x + 70, 110)
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawCentredString(x, 96, signatory["name"])
            pdf.setFont("Helvetica", 9)
            pdf.drawCentredString(x, 84, signatory.get("title", ""))

    _qr(pdf, data.verification_url, width - 150, 44, 96)
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(width - 52, 44, f"ID {data.certificate_id}")
    footer = fill(template.get("footer_text") or "", data.values())
    if footer:
        pdf.setFont("Helvetica", 8)
        pdf.drawString(52, 52, footer)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(52, 42, data.verification_url)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
