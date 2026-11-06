"""Learner purchases from billing-service.

  course.purchased  {"purchase_id", "organization_id", "user_id", "course_id", "valid_days", "amount", "occurred_at"}
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.course_access_service import CourseAccessService


async def handle_course_purchased(db: AsyncSession, payload: dict[str, Any]) -> None:
    await CourseAccessService(db).apply_purchase(payload)
