from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import LanguageKind


class Language(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One supported language or SQL dialect. Adding one is a row here (or an entry in
    runtimes/languages.json, synced by ``python -m app.cli sync-languages``) plus a runtime image on the
    engine — no code change (docs/PRODUCT.md §5.2)."""

    __tablename__ = "languages"

    code: Mapped[str] = mapped_column(String(30), unique=True)  # what clients send, e.g. "python3"
    name: Mapped[str] = mapped_column(String(60))
    version: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(10), default=LanguageKind.PROGRAM, server_default=LanguageKind.PROGRAM)
    # The id this language has on the Judge0 deployment (`GET /languages`); None for SQL dialects.
    engine_language_id: Mapped[int | None] = mapped_column(Integer)
    compiler_options: Mapped[str | None] = mapped_column(String(200))  # e.g. "-std=c++20"
    file_name: Mapped[str] = mapped_column(String(60))  # Main.java, main.py, ...
    editor_mode: Mapped[str] = mapped_column(String(30))  # syntax mode the editor switches to
    starter_template: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Development only: argv for the local engine, e.g. ["python", "{file}"]. Ignored by Judge0.
    local_command: Mapped[list[str] | None] = mapped_column(JSONType)
    # Slower runtimes get more time and memory than the problem's base limits, so no language is penalised.
    time_multiplier: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")
    memory_multiplier: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
