"""Self-registered learners' bought access, from subscription-service.

  course_access.granted / course_access.extended / course_access.expired
      {"access_id", "user_id", "organization_id", "course_id", "starts_at", "ends_at"}
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.learner_access_service import LearnerAccessService


async def handle_course_access_granted(db: AsyncSession, payload: dict[str, Any]) -> None:
    await LearnerAccessService(db).granted(payload)


async def handle_course_access_expired(db: AsyncSession, payload: dict[str, Any]) -> None:
    await LearnerAccessService(db).expired(payload)
