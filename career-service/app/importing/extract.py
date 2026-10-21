"""Plain text out of an uploaded resume: PDF (including a LinkedIn "Save to PDF"), Word .docx, or .txt.

The file is never stored. Its kind is decided by its first bytes, not its name, and the work is bounded: a PDF is read for at
most ``_MAX_PDF_PAGES`` pages and a .docx's document part may not expand past ``_MAX_DOCX_XML_BYTES`` (a zip bomb stops here).
"""

import io
import re
import zipfile
from xml.etree import ElementTree

from app.core.exceptions import ValidationFailedError

_MAX_PDF_PAGES = 10
_MAX_DOCX_XML_BYTES = 10 * 1024 * 1024
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def _unreadable(message: str) -> ValidationFailedError:
    return ValidationFailedError(message, code="UNREADABLE_FILE", details=[{"field": "file", "code": "UNREADABLE_FILE", "message": message}])


def _pdf(content: bytes) -> str:
    from pypdf import PdfReader  # imported here: only an import needs it
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise _unreadable("This PDF is password-protected. Save it without a password and try again.")
        return "\n".join(page.extract_text() or "" for page in reader.pages[:_MAX_PDF_PAGES])
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise _unreadable("This PDF could not be read. Try saving it again, or upload the Word file.") from exc


def _docx(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > _MAX_DOCX_XML_BYTES:
                raise _unreadable("This Word file is too large to read.")
            xml = archive.read(info)
            if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:  # a real .docx never declares entities: refuse expansion attacks outright
                raise _unreadable("This Word file could not be read. Save it as .docx or PDF and try again.")
            root = ElementTree.fromstring(xml)  # noqa: S314 - no DTD/entities allowed above, so nothing can expand or be fetched
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise _unreadable("This Word file could not be read. Save it as .docx or PDF and try again.") from exc
    lines = []
    for paragraph in root.iter(f"{_W}p"):
        lines.append("".join(node.text or "" for node in paragraph.iter(f"{_W}t")))
    return "\n".join(lines)


def extract_text(content: bytes) -> str:
    """The file's text, tidied. Raises ValidationFailedError (422) for an unsupported, unreadable or empty file."""
    if content.startswith(b"%PDF"):
        text = _pdf(content)
    elif content.startswith(b"PK"):
        text = _docx(content)
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationFailedError(
                "Upload a PDF, a Word (.docx) or a text file.", code="UNSUPPORTED_FILE", details=[{"field": "file", "code": "UNSUPPORTED_FILE", "message": "Use PDF, .docx or .txt"}]
            ) from exc
    text = _BLANK_LINES.sub("\n\n", "\n".join(_SPACES.sub(" ", line).strip() for line in text.replace("\r", "\n").split("\n"))).strip()
    if len(text) < 40:
        raise _unreadable("No text was found in this file. If it is a scanned image, upload the original document instead.")
    return text
