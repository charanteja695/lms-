"""Splits lesson text and video transcripts into passages small enough to retrieve precisely and to fit a prompt.

Pure functions, no I/O. Notes are split on blank lines (an author's paragraphs are already the natural unit) and packed
up to ``max_chars``; a paragraph longer than that is split at sentence ends, and a sentence longer than that is cut.
Transcripts arrive as timed segments and are grouped into fixed windows so a citation can say "at 12:40".
"""

import re
from dataclasses import dataclass

_PARAGRAPHS = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Window:
    text: str
    start: float
    end: float


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(paragraph):
        while len(sentence) > max_chars:  # one enormous "sentence" (a code dump, a table): cut it
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current and len(current) + 1 + len(sentence) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip() if current else sentence
    if current:
        pieces.append(current)
    return pieces


def chunk_text(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for raw in _PARAGRAPHS.split(text.strip()):
        paragraph = raw.strip()
        if not paragraph:
            continue
        parts = [paragraph] if len(paragraph) <= max_chars else _split_long(paragraph, max_chars)
        for part in parts:
            if current and len(current) + 2 + len(part) > max_chars:
                chunks.append(current)
                current = part
            else:
                current = f"{current}\n\n{part}" if current else part
    if current:
        chunks.append(current)
    return chunks


def window_transcript(segments: list[tuple[float, float, str]], window_seconds: int, max_chars: int) -> list[Window]:
    """Group ``(start, end, text)`` segments into windows of about ``window_seconds`` (also capped at ``max_chars``).
    Segments are taken in start order; a window starts at its first segment's start and ends at its last segment's end."""
    windows: list[Window] = []
    current: list[tuple[float, float, str]] = []

    def flush() -> None:
        if current:
            windows.append(Window(" ".join(t.strip() for _, _, t in current if t.strip()), current[0][0], current[-1][1]))
            current.clear()

    for start, end, text in sorted(segments, key=lambda s: s[0]):
        if not text.strip():
            continue
        span = end - current[0][0] if current else 0.0
        size = sum(len(t) + 1 for _, _, t in current) + len(text)
        if current and (span > window_seconds or size > max_chars):
            flush()
        current.append((start, end, text))
    flush()
    return windows
