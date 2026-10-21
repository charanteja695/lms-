from typing import Any

from app.domain.enums import ItemKind


def item_label(kind: ItemKind, data: dict[str, Any]) -> str:
    """One line naming an entry, for the list a student picks imported entries from."""
    if kind == ItemKind.EXPERIENCE:
        return " · ".join(x for x in (data.get("title"), data.get("company")) if x)
    if kind == ItemKind.EDUCATION:
        return " · ".join(x for x in (data.get("degree"), data.get("institution")) if x)
    if kind == ItemKind.PROJECT:
        return str(data.get("name", ""))
    if kind == ItemKind.SKILL:
        return str(data.get("name", ""))
    return str(data.get("title", ""))
