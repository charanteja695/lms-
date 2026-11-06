"""Assembling what the model is shown: the student's message wrapped with numbered sources, code and facts, and the
conversation history in the alternating shape a chat model requires. Pure functions.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceLine:
    number: int
    where: str  # "Module > Topic > Lesson", with " (at 12:40)" for a video transcript
    text: str


def clock(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def build_user_message(question: str, *, sources: list[SourceLine], code: str | None, language: str | None, facts: str | None, faq: list[tuple[str, str]]) -> str:
    """The text of the final user turn. Everything but the QUESTION is labelled data the system prompt tells the model not
    to obey; the labels are what let a prompt-injected "ignore your rules" inside a lesson or a code comment be treated as
    content rather than as an instruction."""
    parts: list[str] = []
    if sources:
        parts.append("SOURCES (from the student's course):\n" + "\n\n".join(f"[{s.number}] {s.where}\n{s.text}" for s in sources))
    if faq:
        parts.append("FAQ ENTRIES:\n" + "\n\n".join(f"Q: {q}\nA: {a}" for q, a in faq))
    if facts:
        parts.append("FACTS ABOUT THIS STUDENT (read-only lookups; nothing else is known about them):\n" + facts)
    if code:
        parts.append(f"STUDENT CODE{f' ({language})' if language else ''}:\n```\n{code}\n```")
    parts.append("QUESTION:\n" + question)
    return "\n\n".join(parts)


def normalize_history(turns: list[tuple[str, str]], final_user: str, max_chars: int) -> list[dict[str, str]]:
    """``turns`` are earlier ``(role, content)`` pairs, oldest first. Keeps the newest that fit ``max_chars``, merges
    neighbours with the same role (a message whose answer failed leaves two user turns in a row), drops a leading assistant
    turn, and ends with ``final_user``."""
    kept: list[tuple[str, str]] = []
    used = 0
    for role, content in reversed(turns):
        if used + len(content) > max_chars and kept:
            break
        kept.append((role, content))
        used += len(content)
    kept.reverse()
    merged: list[dict[str, str]] = []
    for role, content in [*kept, ("user", final_user)]:
        if merged and merged[-1]["role"] == role:
            merged[-1]["content"] += "\n\n" + content
        else:
            merged.append({"role": role, "content": content})
    while merged and merged[0]["role"] != "user":
        merged.pop(0)
    return merged
