"""Content moderation (docs/PRODUCT.md §6: "guardrails").

A configured keyword blocklist (``Settings.MODERATION_BLOCKLIST``), not an ML classifier — a placeholder for a real
moderation provider behind the same ``moderate()`` interface. Checked *after* redaction (so a redacted-out email
can't accidentally dodge a phrase match) and before any provider is called: a blocked call costs nothing and is
never sent upstream.
"""

import re


def moderate(text: str, blocklist: list[str]) -> list[str]:
    """The blocklist phrases found in ``text`` (case-insensitive, whole-phrase), if any."""
    lowered = text.lower()
    return [phrase for phrase in blocklist if re.search(r"\b" + re.escape(phrase.lower()) + r"\b", lowered)]
