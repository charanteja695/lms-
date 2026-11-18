"""Shared cross-service entitlement guard for student subscriptions, course browse metadata, and access control."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlparse, urlunparse

import asyncpg


def derive_db_url(settings_db_url: str | None, db_name: str, env_var: str | None = None) -> str:
    if env_var and os.getenv(env_var):
        return os.getenv(env_var, "").replace("postgresql+asyncpg://", "postgresql://")
    if settings_db_url:
        try:
            clean = settings_db_url.replace("postgresql+asyncpg://", "postgresql://")
            parsed = urlparse(clean)
            return urlunparse(parsed._replace(path=f"/{db_name}"))
        except Exception:
            pass
    return f"postgresql://lms:lms@127.0.0.1:5432/{db_name}"


async def get_student_active_plan_state(
    user_id: int,
    *,
    settings_db_url: str | None = None,
) -> dict[str, Any]:
    billing_url = derive_db_url(settings_db_url, "lms_billing", "BILLING_DATABASE_URL")
    conn = await asyncpg.connect(billing_url)
    try:
        # Enforce automatic expiry cleanly at read time
        await conn.execute(
            """
            UPDATE student_subscriptions
            SET status = 'expired', updated_at = NOW()
            WHERE user_id = $1
              AND status = 'active'
              AND ends_at IS NOT NULL
              AND ends_at <= NOW()
            """,
            int(user_id),
        )
        active = await conn.fetchrow(
            """
            SELECT id, public_id, plan_code, plan_name, max_courses,
                   assessment_access_snapshot, certificate_level, starts_at, ends_at
            FROM student_subscriptions
            WHERE user_id = $1
              AND status = 'active'
              AND (ends_at IS NULL OR ends_at > NOW())
            ORDER BY ends_at DESC NULLS LAST
            LIMIT 1
            """,
            int(user_id),
        )
        if active is not None:
            course_rows = await conn.fetch(
                "SELECT course_id FROM student_subscription_courses WHERE subscription_id = $1",
                active["id"],
            )
            assess_raw = active["assessment_access_snapshot"]
            if isinstance(assess_raw, str):
                assess_raw = json.loads(assess_raw)
            return {
                "has_active": True,
                "has_expired": False,
                "subscription_id": str(active["public_id"]),
                "plan_code": active["plan_code"],
                "plan_name": active["plan_name"],
                "max_courses": active["max_courses"],
                "assessment_access": dict(assess_raw or {}),
                "certificate_level": active["certificate_level"],
                "unlocked_course_ids": {int(r["course_id"]) for r in course_rows},
            }

        expired = await conn.fetchrow(
            """
            SELECT id, plan_name
            FROM student_subscriptions
            WHERE user_id = $1 AND status = 'expired'
            ORDER BY ends_at DESC NULLS LAST
            LIMIT 1
            """,
            int(user_id),
        )
        return {
            "has_active": False,
            "has_expired": expired is not None,
            "expired_plan_name": expired["plan_name"] if expired is not None else None,
            "unlocked_course_ids": set(),
            "assessment_access": {},
            "certificate_level": "none",
        }
    finally:
        await conn.close()


async def get_browse_context_for_student(
    course_ids: list[int],
    *,
    user_id: int,
    settings_db_url: str | None = None,
) -> dict[str, Any]:
    billing_url = derive_db_url(settings_db_url, "lms_billing", "BILLING_DATABASE_URL")
    learning_url = derive_db_url(settings_db_url, "lms_learning", "LEARNING_DATABASE_URL")
    batch_course_ids: set[int] = set()
    try:
        lconn = await asyncpg.connect(learning_url)
        try:
            rows = await lconn.fetch(
                """
                SELECT cvr.course_id, b.subscription_id
                FROM enrollments e
                JOIN batches b ON b.id = e.batch_id
                JOIN course_version_refs cvr ON cvr.version_id = b.version_id
                WHERE e.student_user_id = $1
                  AND e.status = 'active'
                  AND cvr.course_id = ANY($2::bigint[])
                """,
                int(user_id),
                [int(cid) for cid in course_ids] or [0],
            )
            for r in rows:
                if int(r["subscription_id"] or 0) > 0:
                    batch_course_ids.add(int(r["course_id"]))
        finally:
            await lconn.close()
    except Exception:
        pass

    plan_state = {
        "has_active": False,
        "has_expired": False,
        "unlocked_course_ids": set(),
    }
    plans: list[dict[str, Any]] = []
    payments_enabled = True
    try:
        plan_state = await get_student_active_plan_state(user_id, settings_db_url=settings_db_url)
        bconn = await asyncpg.connect(billing_url)
        try:
            prows = await bconn.fetch(
                """
                SELECT public_id, code, name, price_paise, billing_duration_days, billing_label,
                       max_courses, features, assessment_access, certificate_level,
                       support_tier, is_recommended, tier_rank
                FROM subscription_plans
                WHERE is_active = TRUE
                ORDER BY display_order ASC, tier_rank ASC, price_paise ASC
                """
            )
            for p in prows:
                plans.append(
                    {
                        "plan_id": str(p["public_id"]),
                        "code": p["code"],
                        "name": p["name"],
                        "price_paise": int(p["price_paise"]),
                        "billing_duration_days": int(p["billing_duration_days"]),
                        "billing_label": p["billing_label"],
                        "max_courses": p["max_courses"],
                        "is_recommended": bool(p["is_recommended"]),
                    }
                )
            ps = await bconn.fetchrow("SELECT payments_enabled FROM payment_settings WHERE id = 1")
            if ps is not None:
                payments_enabled = bool(ps["payments_enabled"])
        finally:
            await bconn.close()
    except Exception:
        pass

    return {
        "batch_enrolled_course_ids": batch_course_ids,
        "plan_state": plan_state,
        "plans": plans,
        "payments_enabled": payments_enabled,
    }


async def check_student_course_entitlement(
    *,
    user_id: int,
    course_id: int,
    assessment_kind: str | None = None,
    require_certificate: bool = False,
    settings_db_url: str | None = None,
    organization_id: int | None = None,
) -> tuple[bool, str | None, str | None]:
    """Checks institutional access, individual course purchases, and optional subscription plans.

    Returns (allowed, error_code, error_message).
    """
    sub_url = derive_db_url(settings_db_url, "lms_subscription", "SUBSCRIPTION_DATABASE_URL")
    learning_url = derive_db_url(settings_db_url, "lms_learning", "LEARNING_DATABASE_URL")
    um_url = derive_db_url(settings_db_url, "lms_user_management", "USER_MANAGEMENT_DATABASE_URL")

    # 1. Check individual course purchase entitlement in lms_subscription.course_access
    try:
        sconn = await asyncpg.connect(sub_url)
        try:
            ca_row = await sconn.fetchrow(
                """
                SELECT id, starts_at, ends_at FROM course_access
                WHERE user_id = $1
                  AND course_id = $2
                  AND status = 'active'
                  AND starts_at <= NOW()
                  AND (ends_at IS NULL OR ends_at > NOW())
                """,
                int(user_id),
                int(course_id),
            )
            if ca_row is not None:
                return True, None, None

            # Resolve organization_id if not provided
            org_id = organization_id
            if org_id is None:
                try:
                    uconn = await asyncpg.connect(um_url)
                    try:
                        urow = await uconn.fetchrow(
                            """
                            SELECT u.institution_id, i.public_id as org_id
                            FROM users u
                            LEFT JOIN institutions i ON i.id = u.institution_id
                            WHERE u.public_id = $1
                            """,
                            int(user_id),
                        )
                        if urow and urow["org_id"]:
                            org_id = int(urow["org_id"])
                    finally:
                        await uconn.close()
                except Exception:
                    pass

            # 2. Check institutional bulk course subscription in lms_subscription.subscriptions
            if org_id:
                sub_row = await sconn.fetchrow(
                    """
                    SELECT id, public_id, seats_total, seats_used, starts_at, ends_at
                    FROM subscriptions
                    WHERE organization_id = $1
                      AND course_id = $2
                      AND status = 'active'
                      AND starts_at <= NOW()
                      AND (ends_at IS NULL OR ends_at > NOW())
                    """,
                    int(org_id),
                    int(course_id),
                )
                if sub_row is not None:
                    seats_total = int(sub_row["seats_total"])
                    seats_used = int(sub_row["seats_used"])

                    # Check if student already holds a reserved seat
                    res = await sconn.fetchrow(
                        """
                        SELECT id FROM seat_reservations
                        WHERE subscription_id = $1
                          AND released_at IS NULL
                          AND reservation_key = $2
                        """,
                        sub_row["id"],
                        str(user_id),
                    )
                    if res is not None:
                        return True, None, None

                    # If not yet reserved, atomically reserve a seat using UPDATE ... WHERE seats_used < seats_total
                    if seats_used >= seats_total:
                        return (
                            False,
                            "SEAT_LIMIT_REACHED",
                            "Seat limit reached for this course in your institution. Please contact your Institution Head.",
                        )

                    import uuid
                    updated = await sconn.fetchrow(
                        """
                        UPDATE subscriptions
                        SET seats_used = seats_used + 1, updated_at = NOW()
                        WHERE id = $1 AND seats_used < seats_total
                        RETURNING seats_used
                        """,
                        sub_row["id"],
                    )
                    if updated is None:
                        return (
                            False,
                            "SEAT_LIMIT_REACHED",
                            "Seat limit reached for this course in your institution. Please contact your Institution Head.",
                        )

                    await sconn.execute(
                        """
                        INSERT INTO seat_reservations (
                            id, subscription_id, reservation_key, created_at
                        ) VALUES (
                            $1, $2, $3, NOW()
                        ) ON CONFLICT (subscription_id, reservation_key) DO NOTHING
                        """,
                        uuid.uuid4(),
                        sub_row["id"],
                        str(user_id),
                    )
                    return True, None, None
        finally:
            await sconn.close()
    except Exception:
        pass

    # 3. Check batch enrollment in learning service
    has_batch_enrollment = False
    has_learner_enrollment = False
    try:
        lconn = await asyncpg.connect(learning_url)
        try:
            rows = await lconn.fetch(
                """
                SELECT b.subscription_id
                FROM enrollments e
                JOIN batches b ON b.id = e.batch_id
                JOIN course_version_refs cvr ON cvr.version_id = b.version_id
                WHERE e.student_user_id = $1
                  AND e.status = 'active'
                  AND cvr.course_id = $2
                """,
                int(user_id),
                int(course_id),
            )
            for r in rows:
                if int(r["subscription_id"] or 0) > 0:
                    has_batch_enrollment = True
                else:
                    has_learner_enrollment = True
        finally:
            await lconn.close()
    except Exception:
        pass

    if has_batch_enrollment or has_learner_enrollment:
        return True, None, None

    # 4. Check optional StudentSubscription plan (Base, Silver, Gold)
    try:
        state = await get_student_active_plan_state(user_id, settings_db_url=settings_db_url)
        if state.get("has_active"):
            if int(course_id) in state.get("unlocked_course_ids", set()):
                if assessment_kind:
                    rules = state.get("assessment_access") or {}
                    if not bool(rules.get(assessment_kind, True)):
                        label = {
                            "chapter_tests": "Chapter Tests",
                            "module_tests": "Module Tests",
                            "final_exam": "Final Exam",
                            "proctoring": "Proctored Exams",
                        }.get(assessment_kind, assessment_kind)
                        return (
                            False,
                            "PLAN_FEATURE_RESTRICTED",
                            f"Your {state['plan_name']} does not include {label}. Upgrade your subscription plan to unlock this assessment.",
                        )
                if require_certificate and str(state.get("certificate_level") or "basic") == "none":
                    return (
                        False,
                        "PLAN_FEATURE_RESTRICTED",
                        f"Your {state['plan_name']} does not include certificates. Upgrade your subscription plan to unlock certificates.",
                    )
                return True, None, None
            return (
                False,
                "COURSE_NOT_UNLOCKED",
                f"Course is not unlocked on your {state['plan_name']}. Unlock it from Course Details to access lessons and exams.",
            )
    except Exception:
        pass

    return (
        False,
        "COURSE_ACCESS_DENIED",
        "An individual course purchase or institutional license is required to access this course.",
    )


async def resolve_course_id_for_assessment_target(
    target_type: str | None,
    target_id: int | None,
    *,
    settings_db_url: str | None = None,
) -> tuple[int | None, str | None]:
    """Maps assessment target (topic / module / course) to (course_public_id, assessment_kind)."""
    if not target_type or not target_id:
        return None, None
    ttype = str(target_type).lower()
    if ttype == "course":
        return int(target_id), "final_exam"

    catalog_url = derive_db_url(settings_db_url, "lms_catalog", "CATALOG_DATABASE_URL")
    try:
        conn = await asyncpg.connect(catalog_url)
        try:
            if ttype == "module":
                cid = await conn.fetchval(
                    """
                    SELECT c.public_id
                    FROM modules m
                    JOIN course_versions cv ON cv.id = m.course_version_id
                    JOIN courses c ON c.id = cv.course_id
                    WHERE m.public_id = $1
                    LIMIT 1
                    """,
                    int(target_id),
                )
                return (int(cid) if cid is not None else None), "module_tests"
            if ttype == "topic":
                cid = await conn.fetchval(
                    """
                    SELECT c.public_id
                    FROM topics t
                    JOIN modules m ON m.id = t.module_id
                    JOIN course_versions cv ON cv.id = m.course_version_id
                    JOIN courses c ON c.id = cv.course_id
                    WHERE t.public_id = $1
                    LIMIT 1
                    """,
                    int(target_id),
                )
                return (int(cid) if cid is not None else None), "chapter_tests"
        finally:
            await conn.close()
    except Exception:
        pass
    return None, None
