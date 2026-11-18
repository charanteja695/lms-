import logging
import os
from typing import Any
from urllib.parse import urlparse, urlunparse

import asyncpg

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_database_url(db_name: str, env_var: str) -> str:
    """Derives an asyncpg-compatible PostgreSQL DSN for the target database.

    Checks the specific environment variable first, then adapts the service's
    DATABASE_URL setting (preserving the host, port, user, and password), and
    falls back to a default localhost connection if settings cannot be loaded.
    """
    env_url = os.getenv(env_var)
    if env_url:
        return env_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        settings_url = get_settings().DATABASE_URL
        settings_url = settings_url.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(settings_url)
        adapted = parsed._replace(path=f"/{db_name}")
        return urlunparse(adapted)
    except Exception as exc:
        logger.warning("Could not derive %s URL from settings: %s; falling back to 127.0.0.1", db_name, exc)
        return f"postgresql://lms:lms@127.0.0.1:5432/{db_name}"


def get_subscription_db_url() -> str:
    return _get_database_url("lms_subscription", "SUBSCRIPTION_DATABASE_URL")


def get_user_management_db_url() -> str:
    return _get_database_url("lms_user_management", "USER_MANAGEMENT_DATABASE_URL")


async def get_student_accessible_course_ids(organization_id: int | None, user_id: int | None = None) -> set[int]:
    """Returns the set of course_ids for which the student has access:
    1. Active subscriptions for the student's institution.
    2. Active individual course purchases for the student.
    """
    course_ids: set[int] = set()
    db_url = get_subscription_db_url()
    try:
        conn = await asyncpg.connect(db_url)
        try:
            if organization_id:
                rows = await conn.fetch("""
                    SELECT course_id FROM subscriptions
                    WHERE organization_id = $1
                      AND status = 'active'
                      AND starts_at <= NOW()
                      AND (ends_at IS NULL OR ends_at > NOW())
                """, int(organization_id))
                course_ids.update(int(r["course_id"]) for r in rows)

            if user_id:
                u_rows = await conn.fetch("""
                    SELECT course_id FROM course_access
                    WHERE user_id = $1
                      AND status = 'active'
                      AND starts_at <= NOW()
                      AND (ends_at IS NULL OR ends_at > NOW())
                """, int(user_id))
                course_ids.update(int(r["course_id"]) for r in u_rows)
        finally:
            await conn.close()
    except Exception as exc:
        logger.error("Failed to query accessible courses for organization %s, user %s from %s: %s", organization_id, user_id, db_url, exc, exc_info=True)
    return course_ids


async def check_student_course_access(organization_id: int | None, course_id: int, user_id: int | None = None) -> bool:
    """Verifies that the student has access to this course:
    1. Active individual purchase in course_access.
    2. Active institutional subscription in subscriptions with seat capacity respected.
    """
    db_url = get_subscription_db_url()
    try:
        conn = await asyncpg.connect(db_url)
        try:
            # 1. Check individual purchase first
            if user_id:
                u_row = await conn.fetchrow("""
                    SELECT id FROM course_access
                    WHERE user_id = $1
                      AND course_id = $2
                      AND status = 'active'
                      AND starts_at <= NOW()
                      AND (ends_at IS NULL OR ends_at > NOW())
                """, int(user_id), int(course_id))
                if u_row is not None:
                    return True

            # 2. Check institutional subscription
            if organization_id:
                sub_row = await conn.fetchrow("""
                    SELECT id, seats_total, seats_used FROM subscriptions
                    WHERE organization_id = $1
                      AND course_id = $2
                      AND status = 'active'
                      AND starts_at <= NOW()
                      AND (ends_at IS NULL OR ends_at > NOW())
                """, int(organization_id), int(course_id))
                if sub_row is not None:
                    seats_total = int(sub_row["seats_total"])
                    seats_used = int(sub_row["seats_used"])
                    if user_id:
                        res = await conn.fetchrow("""
                            SELECT sr.id FROM seat_reservations sr
                            JOIN subscriptions s ON s.id = sr.subscription_id
                            WHERE s.id = $1 AND sr.released_at IS NULL AND sr.reservation_key = $2
                        """, sub_row["id"], str(user_id))
                        if res is not None:
                            return True

                        if seats_used >= seats_total:
                            return False

                        import uuid
                        updated = await conn.fetchrow("""
                            UPDATE subscriptions
                            SET seats_used = seats_used + 1, updated_at = NOW()
                            WHERE id = $1 AND seats_used < seats_total
                            RETURNING seats_used
                        """, sub_row["id"])
                        if updated is None:
                            return False
                        await conn.execute("""
                            INSERT INTO seat_reservations (id, subscription_id, reservation_key, created_at)
                            VALUES ($1, $2, $3, NOW())
                            ON CONFLICT (subscription_id, reservation_key) DO NOTHING
                        """, uuid.uuid4(), sub_row["id"], str(user_id))
                        return True
                    return seats_used < seats_total

            return False
        finally:
            await conn.close()
    except Exception as exc:
        logger.error("Failed to check course access for organization %s, course %s from %s: %s", organization_id, course_id, db_url, exc, exc_info=True)
        return False


async def get_institutions_with_access_for_courses(course_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Returns a mapping from course_id to the list of institutions that have active subscriptions."""
    if not course_ids:
        return {}
    results: dict[int, list[dict[str, Any]]] = {cid: [] for cid in course_ids}
    db_url = get_subscription_db_url()
    try:
        conn = await asyncpg.connect(db_url)
        try:
            rows = await conn.fetch("""
                SELECT s.course_id, s.organization_id, s.seats_total, s.starts_at, s.ends_at,
                       COALESCE(i.name, '') as institution_name
                FROM subscriptions s
                LEFT JOIN institution_refs i ON s.organization_id = i.organization_id
                WHERE s.course_id = ANY($1)
                  AND s.status = 'active'
                  AND starts_at <= NOW()
                  AND (ends_at IS NULL OR ends_at > NOW())
            """, course_ids)
            
            missing_names_orgs = [r["organization_id"] for r in rows if not r["institution_name"]]
            org_names: dict[int, str] = {}
            if missing_names_orgs:
                um_db_url = get_user_management_db_url()
                try:
                    um_conn = await asyncpg.connect(um_db_url)
                    try:
                        um_rows = await um_conn.fetch("""
                            SELECT public_id, name FROM institutions WHERE public_id = ANY($1)
                        """, list(set(missing_names_orgs)))
                        for ur in um_rows:
                            org_names[ur["public_id"]] = ur["name"]
                    finally:
                        await um_conn.close()
                except Exception as um_exc:
                    logger.warning("Failed to lookup institution names from user-management at %s: %s", um_db_url, um_exc)

            for r in rows:
                cid = int(r["course_id"])
                name = r["institution_name"] or org_names.get(r["organization_id"]) or f"Institution {r['organization_id']}"
                results[cid].append({
                    "organization_id": str(r["organization_id"]),
                    "institution_name": name,
                    "seats_total": r["seats_total"],
                    "starts_at": r["starts_at"].isoformat() if r["starts_at"] else None,
                    "ends_at": r["ends_at"].isoformat() if r["ends_at"] else None,
                })
        finally:
            await conn.close()
    except Exception as exc:
        logger.error("Failed to fetch institutions with access for courses %s from %s: %s", course_ids, db_url, exc, exc_info=True)
    return results
