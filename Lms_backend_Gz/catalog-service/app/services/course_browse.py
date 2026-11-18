"""Enriches published courses with module/chapter counts, duration, instructor name, subscription plans, and student access status."""

from typing import Any

import asyncpg
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lms_common.subscription_guard import get_browse_context_for_student

from app.core.config import get_settings
from app.domain.enums import ContentStatus
from app.models.course import Course
from app.models.course_version import CourseVersion
from app.models.module import Module
from app.models.topic import Topic
from app.models.topic_item import TopicItem
from app.schemas.course import BrowsePlanPreviewOut, CourseBrowseOut
from app.services.institution_access import get_user_management_db_url


def _format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "Self-paced"
    mins = max(1, seconds // 60)
    hours, rem_mins = divmod(mins, 60)
    if hours > 0 and rem_mins > 0:
        return f"{hours}h {rem_mins}m"
    if hours > 0:
        return f"{hours}h"
    return f"{rem_mins}m"


async def _fetch_instructor_names(user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    names: dict[int, str] = {}
    try:
        conn = await asyncpg.connect(get_user_management_db_url())
        try:
            rows = await conn.fetch(
                "SELECT public_id, full_name FROM users WHERE public_id = ANY($1::bigint[])",
                list(set(user_ids)),
            )
            for r in rows:
                if r["full_name"]:
                    names[int(r["public_id"])] = str(r["full_name"])
        finally:
            await conn.close()
    except Exception:
        pass
    return names


async def enrich_browse_courses(
    db: AsyncSession,
    courses: list[Course],
    *,
    user_id: int,
    role: str,
) -> list[CourseBrowseOut]:
    if not courses:
        return []

    latest_version_by_course: dict[Any, CourseVersion] = {}
    for c in courses:
        pub_versions = [v for v in (c.versions or []) if v.status == ContentStatus.PUBLISHED]
        if pub_versions:
            latest_version_by_course[c.id] = max(pub_versions, key=lambda v: v.version_number)

    version_ids = [v.id for v in latest_version_by_course.values()]
    stats_by_version: dict[Any, dict[str, int]] = {}
    if version_ids:
        rows = (
            await db.execute(
                select(
                    Module.course_version_id,
                    func.count(distinct(Module.id)).label("modules_count"),
                    func.count(distinct(Topic.id)).label("chapters_count"),
                    func.coalesce(func.sum(TopicItem.duration_seconds), 0).label("duration_seconds"),
                )
                .outerjoin(Topic, Topic.module_id == Module.id)
                .outerjoin(TopicItem, TopicItem.topic_id == Topic.id)
                .where(Module.course_version_id.in_(version_ids))
                .group_by(Module.course_version_id)
            )
        ).all()
        for r in rows:
            stats_by_version[r[0]] = {
                "modules_count": int(r[1] or 0),
                "chapters_count": int(r[2] or 0),
                "duration_seconds": int(r[3] or 0),
            }

    instructors = await _fetch_instructor_names([int(c.created_by) for c in courses])
    ctx = await get_browse_context_for_student(
        [int(c.public_id) for c in courses],
        user_id=user_id,
        settings_db_url=get_settings().DATABASE_URL,
    )

    plan_state = ctx["plan_state"]
    batch_enrolled = ctx["batch_enrolled_course_ids"]
    unlocked_under_plan = plan_state.get("unlocked_course_ids", set())
    plans_preview = [BrowsePlanPreviewOut(**p) for p in ctx["plans"]]
    min_price = min((p.price_paise for p in plans_preview), default=None)
    payments_enabled = bool(ctx["payments_enabled"])

    out: list[CourseBrowseOut] = []
    for c in courses:
        pub_v = latest_version_by_course.get(c.id)
        vstats = stats_by_version.get(pub_v.id if pub_v else None, {})
        dur_sec = vstats.get("duration_seconds", 0)
        cid = int(c.public_id)

        if cid in batch_enrolled:
            access_status = "enrolled"
        elif plan_state.get("has_active") and cid in unlocked_under_plan:
            access_status = "active_plan"
        elif plan_state.get("has_active"):
            max_c = plan_state.get("max_courses")
            if max_c is None or len(unlocked_under_plan) < int(max_c):
                access_status = "eligible_under_plan"
            else:
                access_status = "available" if payments_enabled else "payments_disabled"
        else:
            access_status = "available" if payments_enabled else "payments_disabled"

        out.append(
            CourseBrowseOut(
                public_id=c.public_id,
                title=c.title,
                slug=c.slug,
                summary=c.summary,
                thumbnail_media_id=c.thumbnail_media_id,
                instructor_name=instructors.get(int(c.created_by)) or "ExamLMS Faculty",
                modules_count=vstats.get("modules_count", 0),
                chapters_count=vstats.get("chapters_count", 0),
                duration_seconds=dur_sec,
                duration_label=_format_duration(dur_sec),
                latest_published_version_id=pub_v.public_id if pub_v else None,
                access_status=access_status if role == "student" else "available",
                active_plan_name=plan_state.get("plan_name"),
                min_price_paise=min_price,
                payments_enabled=payments_enabled,
                plans_preview=plans_preview,
            )
        )
    return out
