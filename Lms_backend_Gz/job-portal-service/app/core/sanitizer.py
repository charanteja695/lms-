import html
import re

_DANGEROUS_TAGS_PATTERN = re.compile(
    r"<\s*(script|iframe|object|embed|applet|style|form|input|button|svg|canvas|meta|link)[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)

_SELF_CLOSING_DANGEROUS_PATTERN = re.compile(
    r"<\s*(script|iframe|object|embed|applet|style|form|input|button|svg|canvas|meta|link)[^>]*\/?>",
    re.IGNORECASE,
)

_EVENT_HANDLER_PATTERN = re.compile(
    r"\s*(on[a-zA-Z]+|javascript:|data:)\s*=\s*['\"][^'\"]*['\"]",
    re.IGNORECASE,
)

_INLINE_JS_PATTERN = re.compile(
    r"(javascript|vbscript|data):",
    re.IGNORECASE,
)

_TAG_PATTERN = re.compile(r"<[^>]+>")


def sanitize_html(content: str | None) -> str:
    """Sanitize rich text content by removing unsafe scripts, objects, and event handlers while preserving safe formatting."""
    if not content:
        return ""
    text = str(content)
    # Remove paired dangerous tags with body
    text = _DANGEROUS_TAGS_PATTERN.sub("", text)
    # Remove self-closing or remaining dangerous tags
    text = _SELF_CLOSING_DANGEROUS_PATTERN.sub("", text)
    # Remove on* handlers
    text = _EVENT_HANDLER_PATTERN.sub("", text)
    # Remove javascript: protocol in href/src
    text = _INLINE_JS_PATTERN.sub("", text)
    return text.strip()


def sanitize_bullet(item: str | None, max_length: int = 500) -> str:
    """Sanitize a single bullet item by stripping HTML tags and leading bullet characters."""
    if not item:
        return ""
    text = str(item)
    # Strip HTML
    text = _TAG_PATTERN.sub("", text)
    # Unescape HTML entities
    text = html.unescape(text)
    # Strip leading bullets or numbering
    text = re.sub(r"^[\s•\-\*\u2022\u25E6\u2023]+", "", text)
    # Normalize whitespaces
    text = " ".join(text.split())
    if len(text) > max_length:
        text = text[:max_length].strip()
    return text


def sanitize_bullets(items: list[str] | None, max_length: int = 500) -> list[str]:
    """Sanitize a list of bullets: remove empty and duplicates while preserving order."""
    if not items:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = sanitize_bullet(item, max_length=max_length)
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            cleaned.append(clean)
    return cleaned
