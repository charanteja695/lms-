"""Operator commands (run through ``python -m app.cli``). Kept free of argument parsing and printing so they
can be tested directly."""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.crypto import SecretCipher
from app.domain.enums import LanguageKind
from app.engines.judge0 import Judge0Engine
from app.models.problem import Problem
from app.models.test_case import TestCase
from app.services.language_service import LanguageService

_ROTATE_BATCH = 200


async def sync_languages(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> tuple[int, int]:
    """Upsert runtimes/languages.json. Returns ``(created, updated)``."""
    async with sessionmaker() as db:
        return await LanguageService(db).sync_from_file(Path(settings.LANGUAGES_FILE))


@dataclass(frozen=True, slots=True)
class LanguageCheck:
    code: str
    configured_id: int | None
    engine_name: str | None  # what the engine calls that id; None if the engine has no such id

    @property
    def ok(self) -> bool:
        return self.engine_name is not None


async def verify_languages(
    sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, engine: Judge0Engine | None = None
) -> list[LanguageCheck]:
    """Check every enabled program language's engine id against the running Judge0, so a mismatched id (which
    would silently run code in the wrong language) is caught at deploy time. A human still compares the names."""
    judge0 = engine or Judge0Engine(settings)
    try:
        by_id = {int(entry["id"]): str(entry["name"]) for entry in await judge0.list_languages()}
    finally:
        if engine is None:
            await judge0.aclose()
    async with sessionmaker() as db:
        languages = await LanguageService(db).list_languages()
    return [
        LanguageCheck(language.code, language.engine_language_id, by_id.get(language.engine_language_id or -1))
        for language in languages
        if language.kind == LanguageKind.PROGRAM
    ]


async def rotate_keys(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> int:
    """Re-encrypt every test case and SQL setup script under the newest key, so an old key can be retired.
    Returns how many values were rewritten. Safe to repeat and to interrupt."""
    cipher = SecretCipher.from_settings(settings)
    rewritten = 0
    async with sessionmaker() as db:
        offset = 0
        while True:
            cases = list(
                (await db.execute(select(TestCase).order_by(TestCase.id).offset(offset).limit(_ROTATE_BATCH))).scalars()
            )
            if not cases:
                break
            for case in cases:
                case.input_encrypted = cipher.rotate(case.input_encrypted)
                case.expected_encrypted = cipher.rotate(case.expected_encrypted)
                rewritten += 2
            await db.commit()
            offset += _ROTATE_BATCH
        for problem in (await db.execute(select(Problem).where(Problem.setup_sql_encrypted.is_not(None)))).scalars():
            assert problem.setup_sql_encrypted is not None
            problem.setup_sql_encrypted = cipher.rotate(problem.setup_sql_encrypted)
            rewritten += 1
        await db.commit()
    return rewritten
