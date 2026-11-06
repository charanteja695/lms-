import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import commit_or_conflict
from app.domain.enums import LanguageKind
from app.engines.base import LanguageSpec
from app.models.language import Language

# The fields a catalogue entry or an admin update may set. Everything else in the JSON (e.g. _comment) is ignored.
_FIELDS = (
    "name",
    "version",
    "kind",
    "engine_language_id",
    "compiler_options",
    "file_name",
    "editor_mode",
    "starter_template",
    "local_command",
    "time_multiplier",
    "memory_multiplier",
    "enabled",
    "sort_order",
)


class LanguageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_languages(self, *, include_disabled: bool = False) -> list[Language]:
        stmt = select(Language).order_by(Language.sort_order, Language.code)
        if not include_disabled:
            stmt = stmt.where(Language.enabled.is_(True))
        return list((await self.db.execute(stmt)).scalars())

    async def get(self, code: str, *, must_be_enabled: bool = True) -> Language:
        language = (await self.db.execute(select(Language).where(Language.code == code))).scalar_one_or_none()
        if language is None or (must_be_enabled and not language.enabled):
            raise NotFoundError("Language not found.", code="LANGUAGE_NOT_FOUND")
        return language

    async def create(self, code: str, fields: dict[str, Any]) -> Language:
        if (await self.db.execute(select(Language.id).where(Language.code == code))).first() is not None:
            raise BadRequestError("A language with this code already exists.", code="LANGUAGE_EXISTS")
        language = Language(code=code, **self._clean(fields))
        self.db.add(language)
        await commit_or_conflict(self.db)
        return language

    async def update(self, code: str, fields: dict[str, Any]) -> Language:
        language = await self.get(code, must_be_enabled=False)
        for name, value in self._clean(fields).items():
            setattr(language, name, value)
        await commit_or_conflict(self.db)
        return language

    async def sync_from_file(self, path: Path) -> tuple[int, int]:
        """Upsert the catalogue file's languages. Returns ``(created, updated)``. Idempotent, so it is safe to run
        on every deploy; an admin's runtime changes to a language are overwritten by the file, which is the source
        of truth for the catalogue."""
        entries: list[dict[str, Any]] = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))["languages"]
        existing = {language.code: language for language in await self.list_languages(include_disabled=True)}
        created = updated = 0
        for entry in entries:
            code = entry["code"]
            fields = self._clean({name: entry[name] for name in _FIELDS if name in entry})
            if code in existing:
                for name, value in fields.items():
                    setattr(existing[code], name, value)
                updated += 1
            else:
                self.db.add(Language(code=code, **fields))
                created += 1
        await self.db.commit()
        return created, updated

    @staticmethod
    def _clean(fields: dict[str, Any]) -> dict[str, Any]:
        cleaned = {name: value for name, value in fields.items() if name in _FIELDS}
        if "kind" in cleaned:
            cleaned["kind"] = LanguageKind(cleaned["kind"]).value
        return cleaned

    @staticmethod
    def to_spec(language: Language) -> LanguageSpec:
        return LanguageSpec(
            code=language.code,
            kind=LanguageKind(language.kind),
            engine_language_id=language.engine_language_id,
            file_name=language.file_name,
            local_command=tuple(language.local_command) if language.local_command else None,
            compiler_options=language.compiler_options,
        )
