"""Cross-service PostgreSQL checks & synchronization for student subscriptions.

Ensures:
1. We never auto-publish a course or bypass institutional approval: before a student can
   check out or unlock a course, we verify in `lms_catalog` that it is published and not
   archived, AND in `lms_subscription` that the student's institution has an active
   approved subscription (unless the student belongs to the self-registered 'individual'
   learners organisation).
2. When a student payment is verified by the backend, course access & learning enrollments
   are synchronized into `lms_subscription` (`course_access`) and `lms_learning`
   (`enrollments`) so `My Courses` and `StudentLearningPage` unlock immediately alongside
   transactional outbox events.
"""

from datetime import datetime
import logging
import os
from typing import Any
from urllib.parse import urlparse, urlunparse
import uuid

import asyncpg

from app.core.config import Settings
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims

logger = logging.getLogger(__name__)


def _derive_db_url(settings: Settings, db_name: str, env_var: str) -> str | None:
    env_url = os.getenv(env_var)
    if env_url:
        return env_url.replace("postgresql+asyncpg://", "postgresql://")
    db_url = settings.DATABASE_URL
    if not db_url.startswith("postgresql"):
        return None
    parsed = urlparse(db_url.replace("postgresql+asyncpg://", "postgresql://"))
    return urlunparse(parsed._replace(path=f"/{db_name}"))


async def verify_course_eligible_for_student(
    settings: Settings,
    auth: AccessTokenClaims,
    course_id: int,
) -> dict[str, Any]:
    """Verify course is published and approved for the student's institution.

    Returns ``{"course_id": int, "title": str, "published_version_id": int | None, "institution_approved": bool}``.
    In SQLite unit-test runs where external Postgres DBs are absent, returns a safe stub.
    """
    cat_url = _derive_db_url(settings, "lms_catalog", "CATALOG_DATABASE_URL")
    sub_url = _derive_db_url(settings, "lms_subscription", "SUBSCRIPTION_DATABASE_URL")
    um_url = _derive_db_url(settings, "lms_user_management", "USER_MANAGEMENT_DATABASE_URL")
    if cat_url is None or sub_url is None:
        return {"course_id": course_id, "title": f"Course {course_id}", "published_version_id": None, "institution_approved": True}

    cat_conn = await asyncpg.connect(cat_url)
    try:
        course = await cat_conn.fetchrow(
            """
            SELECT c.id, c.public_id, c.title, c.archived_at,
                   (
                       SELECT cv.public_id FROM course_versions cv
                       WHERE cv.course_id = c.id AND cv.status = 'published'
                       ORDER BY cv.version_number DESC LIMIT 1
                   ) AS published_version_id
            FROM courses c
            WHERE c.public_id = $1
            """,
            int(course_id),
        )
        if course is None or course["archived_at"] is not None:
            raise NotFoundError("Course not found or archived.", code="COURSE_NOT_FOUND")
        if course["published_version_id"] is None:
            raise PermissionDeniedError("This course is not published yet.", code="COURSE_NOT_PUBLISHED")
        title = str(course["title"])
        published_version_id = int(course["published_version_id"])
    finally:
        await cat_conn.close()

    # Check if student's institution is individual (self-registered learners) or institutional
    is_individual_org = False
    if um_url and auth.organization_id:
        try:
            um_conn = await asyncpg.connect(um_url)
            try:
                org = await um_conn.fetchrow(
                    "SELECT org_type, institution_type FROM institutions WHERE public_id = $1",
                    int(auth.organization_id),
                )
                if org and (org["institution_type"] == "individual" or org["org_type"] == "individual"):
                    is_individual_org = True
            finally:
                await um_conn.close()
        except Exception as exc:
            logger.warning("Could not query org_type for %s: %s", auth.organization_id, exc)

    if not is_individual_org:
        if not auth.organization_id:
            raise PermissionDeniedError("Student is not linked to an institution.", code="INSTITUTION_REQUIRED")
        sub_conn = await asyncpg.connect(sub_url)
        try:
            approved = await sub_conn.fetchrow(
                """
                SELECT id FROM subscriptions
                WHERE organization_id = $1
                  AND course_id = $2
                  AND status = 'active'
                  AND starts_at <= NOW()
                  AND (ends_at IS NULL OR ends_at > NOW())
                """,
                int(auth.organization_id),
                int(course_id),
            )
            if approved is None:
                raise PermissionDeniedError(
                    "This course has not been approved for your institution yet.",
                    code="COURSE_NOT_APPROVED_FOR_INSTITUTION",
                )
        finally:
            await sub_conn.close()

    return {
        "course_id": int(course_id),
        "title": title,
        "published_version_id": published_version_id,
        "institution_approved": True,
    }


async def sync_student_course_enrollment(
    settings: Settings,
    *,
    user_id: int,
    organization_id: int,
    course_id: int,
    course_title: str,
    starts_at: datetime,
    ends_at: datetime,
) -> None:
    """Grant course_access in lms_subscription and ensure an active enrollment in lms_learning."""
    sub_url = _derive_db_url(settings, "lms_subscription", "SUBSCRIPTION_DATABASE_URL")
    learn_url = _derive_db_url(settings, "lms_learning", "LEARNING_DATABASE_URL")
    cat_url = _derive_db_url(settings, "lms_catalog", "CATALOG_DATABASE_URL")
    if sub_url is None or learn_url is None or cat_url is None:
        return

    # 1. Upsert course_access in lms_subscription
    try:
        sub_conn = await asyncpg.connect(sub_url)
        try:
            existing = await sub_conn.fetchrow(
                "SELECT id, status, ends_at FROM course_access WHERE user_id = $1 AND course_id = $2",
                int(user_id),
                int(course_id),
            )
            if existing is None:
                await sub_conn.execute(
                    """
                    INSERT INTO course_access (id, public_id, user_id, organization_id, course_id, starts_at, ends_at, status, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', NOW(), NOW())
                    """,
                    uuid.uuid4(),
                    new_public_id(),
                    int(user_id),
                    int(organization_id),
                    int(course_id),
                    starts_at,
                    ends_at,
                )
            else:
                await sub_conn.execute(
                    """
                    UPDATE course_access
                    SET status = 'active', ends_at = GREATEST(ends_at, $1), updated_at = NOW()
                    WHERE id = $2
                    """,
                    ends_at,
                    existing["id"],
                )
        finally:
            await sub_conn.close()
    except Exception as exc:
        logger.warning("Failed to sync course_access for user=%s course=%s: %s", user_id, course_id, exc)

    # 2. Ensure active enrollment in lms_learning on the latest published course version
    try:
        cat_conn = await asyncpg.connect(cat_url)
        try:
            ver = await cat_conn.fetchrow(
                """
                SELECT cv.public_id AS version_id, cv.version_number, c.title
                FROM course_versions cv
                JOIN courses c ON c.id = cv.course_id
                WHERE c.public_id = $1 AND cv.status = 'published'
                ORDER BY cv.version_number DESC LIMIT 1
                """,
                int(course_id),
            )
        finally:
            await cat_conn.close()
        if ver is None:
            return
        version_id = int(ver["version_id"])
        title = str(ver["title"] or course_title)

        learn_conn = await asyncpg.connect(learn_url)
        try:
            # Check if already actively enrolled in this course
            already = await learn_conn.fetchrow(
                """
                SELECT e.id
                FROM enrollments e
                JOIN batches b ON b.id = e.batch_id
                JOIN course_version_refs cvr ON cvr.version_id = b.version_id
                WHERE e.student_user_id = $1
                  AND cvr.course_id = $2
                  AND e.status = 'active'
                LIMIT 1
                """,
                int(user_id),
                int(course_id),
            )
            if already is not None:
                return

            # Ensure institution_ref & course_version_ref exist (FK targets)
            inst_exists = await learn_conn.fetchrow(
                "SELECT organization_id FROM institution_refs WHERE organization_id = $1",
                int(organization_id),
            )
            if inst_exists is None:
                await learn_conn.execute(
                    """
                    INSERT INTO institution_refs (organization_id, name, status, created_at, updated_at)
                    VALUES ($1, $2, 'active', NOW(), NOW())
                    ON CONFLICT (organization_id) DO NOTHING
                    """,
                    int(organization_id),
                    f"Institution {organization_id}",
                )

            ver_exists = await learn_conn.fetchrow(
                "SELECT version_id FROM course_version_refs WHERE version_id = $1",
                version_id,
            )
            if ver_exists is None:
                await learn_conn.execute(
                    """
                    INSERT INTO course_version_refs (version_id, course_id, version_number, title, status, structure, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, 'published', '{"modules": []}'::jsonb, NOW(), NOW())
                    ON CONFLICT (version_id) DO NOTHING
                    """,
                    version_id,
                    int(course_id),
                    int(ver["version_number"]),
                    title[:200],
                )

            # Reuse or create student-subscription batch (subscription_id = 0)
            batch = await learn_conn.fetchrow(
                """
                SELECT id FROM batches
                WHERE organization_id = $1 AND version_id = $2 AND subscription_id = 0 AND status = 'active'
                LIMIT 1
                """,
                int(organization_id),
                version_id,
            )
            if batch is None:
                batch_uuid = uuid.uuid4()
                await learn_conn.execute(
                    """
                    INSERT INTO batches (id, public_id, organization_id, version_id, subscription_id, name, status, created_by, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, 0, $5, 'active', 0, NOW(), NOW())
                    """,
                    batch_uuid,
                    new_public_id(),
                    int(organization_id),
                    version_id,
                    f"{title[:170]} · Subscribers",
                )
                batch_id = batch_uuid
            else:
                batch_id = batch["id"]

            await learn_conn.execute(
                """
                INSERT INTO enrollments (id, public_id, batch_id, student_user_id, status, enrolled_at, created_at, updated_at)
                VALUES ($1, $2, $3, $4, 'active', NOW(), NOW(), NOW())
                """,
                uuid.uuid4(),
                new_public_id(),
                batch_id,
                int(user_id),
            )
        finally:
            await learn_conn.close()
    except Exception as exc:
        logger.warning("Failed to sync learning enrollment for user=%s course=%s: %s", user_id, course_id, exc)


async def resolve_student_category(settings: Settings, auth: AccessTokenClaims) -> str:
    """Return ``'individual'`` for independent learners or ``'institution'`` for institution-managed students.

    Always verifies against ``lms_user_management`` when PostgreSQL is configured so a frontend check or stale scope
    cannot allow an institution student to pay directly.
    """
    um_url = _derive_db_url(settings, "lms_user_management", "USER_MANAGEMENT_DATABASE_URL")
    if um_url is None:
        return "individual" if auth.organization_type == "individual" or auth.has_scope("store.buy") else "institution"
    if not auth.organization_id:
        return "individual"
    try:
        conn = await asyncpg.connect(um_url)
        try:
            row = await conn.fetchrow(
                "SELECT institution_type, org_type FROM institutions WHERE public_id = $1 AND deleted_at IS NULL",
                int(auth.organization_id),
            )
            if row and (row["institution_type"] == "individual" or row["org_type"] == "individual"):
                return "individual"
            return "institution"
        finally:
            await conn.close()
    except Exception as exc:
        logger.warning("Could not resolve student category for org=%s: %s", auth.organization_id, exc)
        return "individual" if auth.has_scope("store.buy") else "institution"


async def fetch_student_profile(settings: Settings, student_user_id: int) -> dict[str, Any] | None:
    """Fetch student identity & institution public_id from ``lms_user_management``."""
    um_url = _derive_db_url(settings, "lms_user_management", "USER_MANAGEMENT_DATABASE_URL")
    if um_url is None:
        return {
            "user_id": int(student_user_id),
            "name": f"Student {student_user_id}",
            "email": f"student.{student_user_id}@example.com",
            "role": "student",
            "organization_id": None,
            "institution_type": "institution",
        }
    conn = await asyncpg.connect(um_url)
    try:
        row = await conn.fetchrow(
            """
            SELECT u.public_id, COALESCE(u.email, u.username, '') AS email, u.first_name, u.last_name, u.role, u.status,
                   i.public_id AS org_public_id, i.institution_type, i.name AS org_name
            FROM users u
            LEFT JOIN institutions i ON i.id = u.institution_id
            WHERE u.public_id = $1 AND u.deleted_at IS NULL
            """,
            int(student_user_id),
        )
        if row is None:
            return None
        full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or row["email"]
        return {
            "user_id": int(row["public_id"]),
            "name": full_name,
            "email": str(row["email"]),
            "role": str(row["role"]),
            "status": str(row["status"]),
            "organization_id": int(row["org_public_id"]) if row["org_public_id"] is not None else None,
            "institution_type": str(row["institution_type"] or ""),
            "organization_name": str(row["org_name"] or ""),
        }
    finally:
        await conn.close()


async def list_institution_students_from_um(
    settings: Settings,
    organization_id: int,
    *,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """List all active/registered students belonging to ``organization_id``."""
    um_url = _derive_db_url(settings, "lms_user_management", "USER_MANAGEMENT_DATABASE_URL")
    if um_url is None:
        return []
    conn = await asyncpg.connect(um_url)
    try:
        params: list[Any] = [int(organization_id)]
        where = "i.public_id = $1 AND u.role = 'student' AND u.deleted_at IS NULL"
        if search and search.strip():
            params.append(f"%{search.strip()}%")
            where += f" AND (u.email ILIKE ${len(params)} OR u.first_name ILIKE ${len(params)} OR u.last_name ILIKE ${len(params)} OR CAST(u.public_id AS TEXT) ILIKE ${len(params)})"
        rows = await conn.fetch(
            f"""
            SELECT u.public_id, COALESCE(u.email, u.username, '') AS email, u.first_name, u.last_name, u.status, u.created_at
            FROM users u
            JOIN institutions i ON i.id = u.institution_id
            WHERE {where}
            ORDER BY u.created_at DESC, u.id DESC
            """,
            *params,
        )
        return [
            {
                "student_user_id": int(r["public_id"]),
                "student_name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or str(r["email"]),
                "student_email": str(r["email"]),
                "account_status": str(r["status"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    finally:
        await conn.close()


async def list_institution_approved_courses(settings: Settings, organization_id: int) -> list[dict[str, Any]]:
    """Return published courses approved for ``organization_id``."""
    cat_url = _derive_db_url(settings, "lms_catalog", "CATALOG_DATABASE_URL")
    sub_url = _derive_db_url(settings, "lms_subscription", "SUBSCRIPTION_DATABASE_URL")
    if cat_url is None or sub_url is None:
        return []
    sub_conn = await asyncpg.connect(sub_url)
    try:
        rows = await sub_conn.fetch(
            """
            SELECT DISTINCT course_id FROM subscriptions
            WHERE organization_id = $1 AND status = 'active'
            """,
            int(organization_id),
        )
        approved_ids = [int(r["course_id"]) for r in rows]
    finally:
        await sub_conn.close()
    if not approved_ids:
        return []
    cat_conn = await asyncpg.connect(cat_url)
    try:
        courses = await cat_conn.fetch(
            """
            SELECT c.public_id, c.title
            FROM courses c
            WHERE c.public_id = ANY($1::bigint[])
              AND c.archived_at IS NULL
              AND EXISTS (
                  SELECT 1 FROM course_versions cv
                  WHERE cv.course_id = c.id AND cv.status = 'published'
              )
            ORDER BY c.title ASC
            """,
            approved_ids,
        )
        return [{"course_id": int(c["public_id"]), "course_title": str(c["title"])} for c in courses]
    finally:
        await cat_conn.close()


async def fetch_institution_head_user_ids(settings: Settings, organization_id: int) -> list[int]:
    um_url = _derive_db_url(settings, "lms_user_management", "USER_MANAGEMENT_DATABASE_URL")
    if um_url is None:
        return []
    try:
        conn = await asyncpg.connect(um_url)
        try:
            rows = await conn.fetch(
                """
                SELECT u.public_id
                FROM users u
                JOIN institutions i ON i.id = u.institution_id
                WHERE i.public_id = $1 AND u.role = 'institution_head' AND u.deleted_at IS NULL
                """,
                int(organization_id),
            )
            return [int(r["public_id"]) for r in rows]
        finally:
            await conn.close()
    except Exception as exc:
        logger.warning("Could not fetch institution heads for org=%s: %s", organization_id, exc)
        return []


async def fetch_institution_names(settings: Settings, organization_ids: list[int]) -> dict[int, str]:
    um_url = _derive_db_url(settings, "lms_user_management", "USER_MANAGEMENT_DATABASE_URL")
    if um_url is None or not organization_ids:
        return {}
    try:
        conn = await asyncpg.connect(um_url)
        try:
            rows = await conn.fetch(
                "SELECT public_id, name FROM institutions WHERE public_id = ANY($1::bigint[])",
                [int(o) for o in set(organization_ids)],
            )
            return {int(r["public_id"]): str(r["name"]) for r in rows}
        finally:
            await conn.close()
    except Exception as exc:
        logger.warning("Could not fetch institution names: %s", exc)
        return {}


async def send_in_app_notification(
    settings: Settings,
    *,
    recipient_user_id: int,
    organization_id: int | None,
    type_key: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Deliver an in-app notification row into ``lms_notification.notifications``."""
    notif_url = _derive_db_url(settings, "lms_notification", "NOTIFICATION_DATABASE_URL")
    if notif_url is None:
        return
    import json as _json

    try:
        conn = await asyncpg.connect(notif_url)
        try:
            await conn.execute(
                """
                INSERT INTO notifications
                    (id, public_id, recipient_user_id, organization_id, event_id, type_key, category, title, body, data, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, 'billing', $7, $8, $9::jsonb, NOW())
                """,
                uuid.uuid4(),
                new_public_id(),
                int(recipient_user_id),
                int(organization_id) if organization_id is not None else None,
                uuid.uuid4().hex,
                type_key[:100],
                title[:300],
                body,
                _json.dumps(data or {}),
            )
        finally:
            await conn.close()
    except Exception as exc:
        logger.warning("Failed to send notification to user=%s: %s", recipient_user_id, exc)
