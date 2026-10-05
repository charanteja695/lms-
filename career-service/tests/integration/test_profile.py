from sqlalchemy import select

from app.models.outbox_event import OutboxEvent
from app.models.profile import ProfileItem
from tests.conftest import (
    CERT,
    CERT_2,
    COURSE,
    COURSE_2,
    ORG_B,
    STAFF_B,
    STUDENT,
    STUDENT_2,
    attempt_payload,
    certificate_payload,
    fill_profile,
    seed_student,
    user_payload,
)

API = "/api/v1"


async def events(sessionmaker, kind: str | None = None) -> list[dict]:
    async with sessionmaker() as db:
        rows = (await db.execute(select(OutboxEvent).order_by(OutboxEvent.created_at))).scalars()
        return [r.payload | {"_type": r.event_type} for r in rows if kind is None or r.event_type == kind]


# ---------------------------------------------------------------- self-declared items
async def test_profile_starts_empty_with_verified_details_from_user_management(client, who, send_event):
    await send_event("user.created", user_payload())
    who.student()
    body = (await client.get(f"{API}/profile")).json()
    assert body["personal"] == {"name": "Asha Rao", "email": "asha@example.com", "name_verified": True}
    assert body["items"] == [] and body["profile"]["revision"] == 0
    who.staff()
    assert (await client.get(f"{API}/profile")).status_code == 403  # students only


async def test_self_declared_items_are_validated_labelled_and_editable(client, who, sessionmaker):
    who.student()
    ids = await fill_profile(client)
    profile = (await client.get(f"{API}/profile")).json()
    assert profile["profile"]["headline"] == "Aspiring backend developer" and profile["profile"]["links"] == [{"label": "GitHub", "url": "https://github.com/asha"}]
    by_kind = {i["kind"]: i for i in profile["items"]}
    assert by_kind["education"]["verified"] is False and by_kind["education"]["label"] == "Self-declared"
    bad = await client.post(f"{API}/profile/items", json={"kind": "education", "data": {"institution": "X", "degree": "B.Tech", "start_date": "2024-13"}})
    assert bad.status_code == 422 and bad.json()["details"][0]["field"] == "data.start_date"
    backwards = await client.post(f"{API}/profile/items", json={"kind": "experience", "data": {"company": "A", "title": "B", "start_date": "2025-05", "end_date": "2025-01"}})
    assert backwards.status_code == 422
    extra = await client.post(f"{API}/profile/items", json={"kind": "skill", "data": {"name": "Go", "level": 9}})
    assert extra.status_code == 422
    too_many = await client.post(f"{API}/profile/items", json={"kind": "experience", "data": {"company": "A", "title": "B", "bullets": ["x"] * 9}})
    assert too_many.status_code == 422
    edited = await client.patch(f"{API}/profile/items/{ids['py']}", json={"data": {"name": "Python 3"}})
    assert edited.status_code == 200 and edited.json()["item"]["data"]["name"] == "Python 3"
    assert (await client.delete(f"{API}/profile/items/{ids['sql']}")).status_code == 200
    assert {i["item_id"] for i in (await client.get(f"{API}/profile")).json()["items"]} == set(ids.values()) - {ids["sql"]}
    who.student(STUDENT_2)
    assert (await client.patch(f"{API}/profile/items/{ids['py']}", json={"data": {"name": "Hijack"}})).status_code == 404  # someone else's item


async def test_verified_kinds_cannot_be_added_by_hand(client, who):
    who.student()
    response = await client.post(f"{API}/profile/items", json={"kind": "certificate", "data": {"course_id": "1"}})
    assert response.status_code == 403 and response.json()["code"] == "VERIFIED_KIND"


async def test_reorder_needs_every_item_once(client, who):
    who.student()
    ids = await fill_profile(client)
    ok = await client.put(f"{API}/profile/items/order", json={"kind": "skill", "item_ids": [ids["sql"], ids["py"]]})
    assert [i["item_id"] for i in ok.json()["items"]] == [ids["sql"], ids["py"]]
    assert (await client.put(f"{API}/profile/items/order", json={"kind": "skill", "item_ids": [ids["sql"]]})).status_code == 409
    assert (await client.put(f"{API}/profile/items/order", json={"kind": "skill", "item_ids": [ids["sql"], ids["sql"]]})).status_code == 409


async def test_item_limit_per_kind(client, who, settings):
    who.student()
    for n in range(settings.MAX_PROFILE_ITEMS_PER_KIND):
        assert (await client.post(f"{API}/profile/items", json={"kind": "skill", "data": {"name": f"Skill {n}"}})).status_code == 201
    over = await client.post(f"{API}/profile/items", json={"kind": "skill", "data": {"name": "One too many"}})
    assert over.status_code == 409 and over.json()["code"] == "TOO_MANY_ITEMS"


async def test_every_change_bumps_the_revision_and_emits_skill_profile_updated(client, who, sessionmaker):
    who.student()
    await fill_profile(client)
    updates = await events(sessionmaker, "skill_profile.updated")
    assert [u["revision"] for u in updates] == list(range(1, len(updates) + 1)) and len(updates) == 7
    assert updates[-1]["self_declared"]["skill"] == 2 and updates[-1]["verified"] == {"certificate": 0, "course": 0, "skill_score": 0} and updates[-1]["user_id"] == str(STUDENT)


# ---------------------------------------------------------------- verified items from events
async def test_certificate_and_course_appear_as_verified_read_only_items(client, who, send_event, sessionmaker):
    await seed_student(send_event)
    await send_event("certificate.issued", certificate_payload())
    who.student()
    items = {i["kind"]: i for i in (await client.get(f"{API}/profile")).json()["items"]}
    cert = items["certificate"]
    assert cert["verified"] is True and cert["label"] == "Verified" and cert["derived"]["course_title"] == "Python Programming" and cert["data"]["grade"] == "A"
    assert items["course"]["data"]["completed_at"] == "2026-08-30"
    for item in (cert, items["course"]):
        edit = await client.patch(f"{API}/profile/items/{item['item_id']}", json={"data": {"name": "x"}})
        assert edit.status_code == 403 and edit.json()["code"] == "VERIFIED_ITEM_READONLY"
        assert (await client.delete(f"{API}/profile/items/{item['item_id']}")).status_code == 403
    update = (await events(sessionmaker, "skill_profile.updated"))[-1]
    assert update["verified"]["certificate"] == 1 and update["verified"]["course"] == 1


async def test_certificate_events_are_idempotent_and_out_of_order_safe(client, who, send_event, sessionmaker):
    # the certificate arrives before the student and the course are known
    await send_event("certificate.issued", certificate_payload(), event_id="evt-cert-1")
    await send_event("certificate.issued", certificate_payload(), event_id="evt-cert-1")  # a redelivery
    await send_event("certificate.issued", certificate_payload())  # the same certificate again under a new event id
    async with sessionmaker() as db:
        assert len((await db.execute(select(ProfileItem).where(ProfileItem.kind == "certificate"))).scalars().all()) == 1
    assert len(await events(sessionmaker, "skill_profile.updated")) == 1  # the repeat changed nothing, so said nothing
    who.student()
    assert (await client.get(f"{API}/profile")).json()["items"][0]["derived"]["course_title"] == "Course"  # title unknown yet
    await send_event("course.published", {"course_id": str(COURSE), "title": "Python Programming"})
    assert {i["derived"]["course_title"] for i in (await client.get(f"{API}/profile")).json()["items"]} == {"Python Programming"}


async def test_a_revoked_certificate_leaves_the_profile_and_the_course_with_it(client, who, send_event):
    await seed_student(send_event)
    await send_event("certificate.issued", certificate_payload())
    await send_event("certificate.issued", certificate_payload(CERT_2, COURSE_2))
    await send_event("certificate.revoked", {"certificate_id": str(CERT), "student_user_id": str(STUDENT), "course_id": str(COURSE), "reason": "integrity"})
    who.student()
    items = (await client.get(f"{API}/profile")).json()["items"]
    revoked = [i for i in items if not i["active"]]
    assert {(i["kind"], i["inactive_reason"]) for i in revoked} == {("certificate", "certificate revoked"), ("course", "certificate revoked")}
    assert {i["data"]["course_id"] for i in items if i["active"]} == {str(COURSE_2)}
    await send_event("certificate.issued", certificate_payload())  # re-issued: back on the profile
    assert all(i["active"] for i in (await client.get(f"{API}/profile")).json()["items"])


async def test_a_second_valid_certificate_keeps_the_course(client, who, send_event):
    await seed_student(send_event)
    await send_event("certificate.issued", certificate_payload(CERT))
    await send_event("certificate.issued", certificate_payload(CERT_2))  # a re-issue for the same course
    await send_event("certificate.revoked", {"certificate_id": str(CERT), "student_user_id": str(STUDENT), "course_id": str(COURSE), "reason": "replaced"})
    who.student()
    active = {i["kind"] for i in (await client.get(f"{API}/profile")).json()["items"] if i["active"]}
    assert active == {"certificate", "course"}


async def test_skill_score_is_the_best_passed_released_result(client, who, send_event):
    await seed_student(send_event)
    who.student()

    async def score() -> dict | None:
        found = [i for i in (await client.get(f"{API}/profile")).json()["items"] if i["kind"] == "skill_score" and i["active"]]
        return found[0]["data"] if found else None

    await send_event("attempt.finalized", attempt_payload(1, percent=40, result="failed"))
    assert await score() is None  # a failed attempt is not a skill
    await send_event("attempt.finalized", attempt_payload(2, percent=72.5))
    await send_event("attempt.finalized", attempt_payload(3, percent=88, kind="module"))
    await send_event("attempt.finalized", attempt_payload(4, percent=99, kind="practice"))  # practice never counts
    await send_event("attempt.finalized", attempt_payload(5, percent=95, kind="hiring"))  # neither does an employer's test
    assert (await score()) == {"course_id": str(COURSE), "best_percent": 88.0, "attempts": 2}
    await send_event("attempt.finalized", attempt_payload(3, percent=88, kind="module", result="invalidated", revision=2))  # an integrity ruling
    assert (await score()) == {"course_id": str(COURSE), "best_percent": 72.5, "attempts": 1}
    await send_event("attempt.finalized", attempt_payload(3, percent=88, kind="module", revision=1))  # an older release arriving late changes nothing
    assert (await score())["best_percent"] == 72.5
    await send_event("attempt.finalized", attempt_payload(2, percent=72.5, result="invalidated", revision=2))
    assert await score() is None  # nothing valid left: the item is deactivated, not shown as 0


async def test_percentile_needs_a_cohort(client, who, send_event, settings):
    await seed_student(send_event)
    for n, (user, percent) in enumerate(((STUDENT, 90.0), (STUDENT_2, 70.0), (STUDENT_2 + 1, 50.0), (STUDENT_2 + 2, 90.0))):
        await send_event("attempt.finalized", attempt_payload(100 + n, user=user, percent=percent))
    who.student()
    score = next(i for i in (await client.get(f"{API}/profile")).json()["items"] if i["kind"] == "skill_score")
    assert score["derived"]["cohort_size"] == 4 and score["derived"]["percentile"] == 75  # (2 below + half of 2 equal) / 4
    who.student(STUDENT_2 + 1)
    lowest = next(i for i in (await client.get(f"{API}/profile")).json()["items"] if i["kind"] == "skill_score")
    assert lowest["derived"]["percentile"] == 12  # nobody below, half of one equal: 12.5 rounds to 12
    await send_event("attempt.finalized", attempt_payload(200, user=STUDENT_2 + 5, course=COURSE_2, percent=61))
    who.student(STUDENT_2 + 5)
    small = next(i for i in (await client.get(f"{API}/profile")).json()["items"] if i["kind"] == "skill_score")
    assert small["derived"]["percentile"] is None and small["derived"]["cohort_size"] == 1 and settings.PERCENTILE_MIN_COHORT == 3


# ---------------------------------------------------------------- reading someone else's profile
async def test_staff_and_managers_read_a_students_profile_within_their_reach(client, who, send_event):
    await seed_student(send_event)
    await send_event("certificate.issued", certificate_payload())
    who.staff()
    seen = await client.get(f"{API}/students/{STUDENT}/profile")
    assert seen.status_code == 200 and seen.json()["personal"]["name"] == "Asha Rao" and seen.json()["items"][0]["verified"] is True
    who.staff(STAFF_B, ORG_B)
    assert (await client.get(f"{API}/students/{STUDENT}/profile")).status_code == 403  # another institution
    who.manager()
    assert (await client.get(f"{API}/students/{STUDENT}/profile")).status_code == 200
    who.other_admin()
    assert (await client.get(f"{API}/students/{STUDENT}/profile")).status_code == 403
    who.student(STUDENT_2)
    assert (await client.get(f"{API}/students/{STUDENT}/profile")).status_code == 403
    who.student()
    assert (await client.get(f"{API}/students/{STUDENT}/profile")).status_code == 200  # oneself
    who.manager()
    assert (await client.get(f"{API}/students/1755000000059999/profile")).status_code == 404


async def test_skill_profile_updated_carries_matching_facts(client, who, send_event, sessionmaker):
    await seed_student(send_event)
    await send_event("certificate.issued", certificate_payload())
    who.student()
    await fill_profile(client)
    facts = (await events(sessionmaker, "skill_profile.updated"))[-1]["facts"]
    assert set(facts["skills"]) == {"Python", "SQL"} and facts["graduation_year"] == 2026 and facts["certificates"] == [str(COURSE)] and facts["location"] == "Chennai, India"
    assert facts["technologies"] == ["FastAPI", "PostgreSQL", "Python"] and facts["experience_months"] == 3
    assert "Asha" not in str(facts) and "asha@example.com" not in str(facts) and "Anna University" not in str(facts)


async def test_internal_snapshot_freezes_the_resume_that_was_sent(client, who, send_event, sessionmaker):
    from tests.conftest import INTERNAL_TOKEN
    from tests.integration.test_resumes import ready_student

    _, rid = await ready_student(client, who, send_event)
    headers = {"X-Internal-Service-Token": INTERNAL_TOKEN}
    body = {"user_id": str(STUDENT), "label": "Applied to Acme: Backend Developer"}
    assert (await client.post(f"{API}/internal/resumes/{rid}/snapshot", json=body)).status_code == 403
    done = await client.post(f"{API}/internal/resumes/{rid}/snapshot", json=body, headers=headers)
    assert done.status_code == 201 and done.json()["version_no"] == 1 and done.json()["document"]["personal"]["name"] == "Asha Rao" and done.json()["title"] == "Backend Developer"
    assert (await client.post(f"{API}/internal/resumes/{rid}/snapshot", json={**body, "user_id": str(STUDENT_2)}, headers=headers)).status_code == 404  # not their resume
    assert (await client.post(f"{API}/internal/resumes/nope/snapshot", json=body, headers=headers)).status_code == 404
    versions = (await client.get(f"{API}/resumes/{rid}/versions")).json()["versions"]
    assert [v["label"] for v in versions] == ["Applied to Acme: Backend Developer"]  # the student sees what was sent
