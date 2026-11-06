from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.session import commit_or_conflict
from app.models.language import Language
from app.models.problem import Problem
from app.models.saved_code import SavedCode


class SavedCodeService:
    """A student's work in progress per problem and language (docs/PRODUCT.md §5.2)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, user_id: int, problem: Problem, language: Language) -> SavedCode | None:
        return (
            await self.db.execute(
                select(SavedCode).where(
                    SavedCode.user_id == user_id, SavedCode.problem_id == problem.id, SavedCode.language_code == language.code
                )
            )
        ).scalar_one_or_none()

    async def save(self, user_id: int, problem: Problem, language: Language, source: str) -> SavedCode:
        saved = await self.get(user_id, problem, language)
        if saved is None:
            saved = SavedCode(user_id=user_id, problem_id=problem.id, language_code=language.code, source=source)
            self.db.add(saved)
        else:
            saved.source = source
            saved.updated_at = utcnow()
        await commit_or_conflict(self.db)
        return saved
