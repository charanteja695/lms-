import asyncpg
from typing import Any

DATABASE_URL = "postgresql://lms:lms@127.0.0.1:5432/lms_subscription"
UM_DATABASE_URL = "postgresql://lms:lms@127.0.0.1:5432/lms_user_management"


async def get_student_accessible_course_ids(organization_id: int | None) -> set[int]:
    """Returns the set of course_ids for which the student's institution has an active subscription."""
    if not organization_id:
        return set()
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            rows = await conn.fetch("""
                SELECT course_id FROM subscriptions
                WHERE organization_id = $1
                  AND status = 'active'
                  AND starts_at <= NOW()
                  AND (ends_at IS NULL OR ends_at > NOW())
            """, int(organization_id))
            return {int(r["course_id"]) for r in rows}
        finally:
            await conn.close()
    except Exception:
        return set()


async def check_student_course_access(organization_id: int | None, course_id: int) -> bool:
    """Verifies that the student's institution has an active subscription for this specific course."""
    if not organization_id:
        return False
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            row = await conn.fetchrow("""
                SELECT id FROM subscriptions
                WHERE organization_id = $1
                  AND course_id = $2
                  AND status = 'active'
                  AND starts_at <= NOW()
                  AND (ends_at IS NULL OR ends_at > NOW())
            """, int(organization_id), int(course_id))
            return row is not None
        finally:
            await conn.close()
    except Exception:
        return False


async def get_institutions_with_access_for_courses(course_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Returns a mapping from course_id to the list of institutions that have active subscriptions."""
    if not course_ids:
        return {}
    results: dict[int, list[dict[str, Any]]] = {cid: [] for cid in course_ids}
    try:
        conn = await asyncpg.connect(DATABASE_URL)
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
                try:
                    um_conn = await asyncpg.connect(UM_DATABASE_URL)
                    try:
                        um_rows = await um_conn.fetch("""
                            SELECT public_id, name FROM institutions WHERE public_id = ANY($1)
                        """, list(set(missing_names_orgs)))
                        for ur in um_rows:
                            org_names[ur["public_id"]] = ur["name"]
                    finally:
                        await um_conn.close()
                except Exception:
                    pass

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
    except Exception:
        pass
    return results
