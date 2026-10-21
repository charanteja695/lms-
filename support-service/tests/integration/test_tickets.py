from datetime import timedelta

from sqlalchemy import select, update

from app.core.ids import parse_public_id
from app.core.time import utcnow
from app.models.outbox_event import OutboxEvent as Outbox
from app.models.ticket import Ticket, TicketEvent
from app.services.ticket_service import sweep_sla
from tests.conftest import COURSE, ORG_A, ORG_B, STAFF_A, STAFF_A2, STAFF_B, STUDENT, STUDENT_2, SUPPORT, open_ticket

API = "/api/v1"


async def event_types(sessionmaker) -> list[str]:
    async with sessionmaker() as db:
        return [e.event_type for e in (await db.execute(select(Outbox).order_by(Outbox.created_at))).scalars()]


async def backdate(sessionmaker, ticket_id: str, **columns) -> None:
    async with sessionmaker() as db:
        await db.execute(update(Ticket).where(Ticket.public_id == int(ticket_id)).values(**columns))
        await db.commit()


# ---------------------------------------------------------------- opening and routing
async def test_categories_route_to_the_right_queue(client, who):
    who.student()
    assert (await open_ticket(client, category="learning"))["queue"] == "batch_staff"
    assert (await open_ticket(client, category="technical"))["queue"] == "platform_support"
    assert (await open_ticket(client, category="billing"))["queue"] == "platform_support"
    integrity = await open_ticket(client, category="integrity")
    assert integrity["queue"] == "exam_team" and integrity["priority"] == "high"
    assert integrity["first_response_due_at"] and integrity["status"] == "open"


async def test_idempotency_key_returns_the_same_ticket(client, who, sessionmaker):
    who.student()
    first = await open_ticket(client, key="retry-key-0001")
    second = (await client.post(f"{API}/tickets", json={"subject": "same thing", "description": "again", "category": "learning"}, headers={"Idempotency-Key": "retry-key-0001"})).json()
    assert second["ticket"]["ticket_id"] == first["ticket_id"]
    assert (await event_types(sessionmaker)).count("ticket.created") == 1
    who.student(STUDENT_2)  # keys are per person
    other = await open_ticket(client, key="retry-key-0001")
    assert other["ticket_id"] != first["ticket_id"]


async def test_only_students_open_tickets_and_bad_input_is_rejected(client, who):
    who.staff()
    assert (await client.post(f"{API}/tickets", json={"subject": "hello there", "description": "x", "category": "other"})).status_code == 403
    who.student()
    assert (await client.post(f"{API}/tickets", json={"subject": "hi", "description": "x", "category": "other"})).status_code == 422
    assert (await client.post(f"{API}/tickets", json={"subject": "hello there", "description": "x", "category": "nope"})).status_code == 422


async def test_students_see_only_their_own_tickets(client, who):
    who.student()
    mine = await open_ticket(client)
    who.student(STUDENT_2)
    assert (await client.get(f"{API}/tickets/{mine['ticket_id']}")).status_code == 404
    assert (await client.get(f"{API}/tickets")).json()["tickets"] == []
    who.student()
    listing = (await client.get(f"{API}/tickets")).json()
    assert [t["ticket_id"] for t in listing["tickets"]] == [mine["ticket_id"]]
    assert (await client.get(f"{API}/tickets/not-an-id")).status_code == 404


# ---------------------------------------------------------------- the queue and who may see what
async def test_queue_visibility_by_role(client, who):
    who.student()
    learning = await open_ticket(client, category="learning")
    technical = await open_ticket(client, category="technical")
    integrity = await open_ticket(client, category="integrity")
    who.student(STUDENT_2, organization_id=ORG_B)
    other_org = await open_ticket(client, category="learning")

    def ids(response) -> set[str]:
        return {t["ticket_id"] for t in response.json()["tickets"]}

    who.staff()
    assert ids(await client.get(f"{API}/agent/tickets")) == {learning["ticket_id"]}
    who.staff(STAFF_B, ORG_B)
    assert ids(await client.get(f"{API}/agent/tickets")) == {other_org["ticket_id"]}
    who.exam_team()
    assert ids(await client.get(f"{API}/agent/tickets")) == {integrity["ticket_id"]}
    who.support()
    assert len(ids(await client.get(f"{API}/agent/tickets"))) == 4
    assert ids(await client.get(f"{API}/agent/tickets?queue=platform_support")) == {technical["ticket_id"]}
    who.student()
    assert (await client.get(f"{API}/agent/tickets")).status_code == 403
    who.staff()
    assert (await client.get(f"{API}/agent/tickets/{technical['ticket_id']}")).status_code == 404  # not their queue
    assert (await client.get(f"{API}/agent/tickets/{other_org['ticket_id']}")).status_code == 404


async def test_queue_filters_and_sorting(client, who, sessionmaker):
    who.student()
    low = await open_ticket(client, category="technical", subject="printer problem")
    urgent = await open_ticket(client, category="technical", subject="cannot log in")
    who.support()
    await client.patch(f"{API}/agent/tickets/{urgent['ticket_id']}", json={"priority": "urgent"})
    ordered = [t["ticket_id"] for t in (await client.get(f"{API}/agent/tickets?sort=due")).json()["tickets"]]
    assert ordered == [urgent["ticket_id"], low["ticket_id"]]
    assert [t["ticket_id"] for t in (await client.get(f"{API}/agent/tickets?q=printer")).json()["tickets"]] == [low["ticket_id"]]
    assert [t["ticket_id"] for t in (await client.get(f"{API}/agent/tickets?assignee=unassigned&priority=urgent")).json()["tickets"]] == [urgent["ticket_id"]]
    assert (await client.get(f"{API}/agent/tickets?assignee=abc")).status_code == 422
    assert (await client.get(f"{API}/agent/tickets?assignee=me")).json()["tickets"] == []


# ---------------------------------------------------------------- replying, notes, status
async def test_reply_flow_and_internal_notes_stay_hidden(client, who, sessionmaker):
    who.student()
    ticket = await open_ticket(client, category="learning")
    tid = ticket["ticket_id"]
    who.staff()
    note = await client.post(f"{API}/agent/tickets/{tid}/replies", json={"body": "Looks like they skipped lesson 2.", "internal": True})
    assert note.status_code == 201
    after_note = (await client.get(f"{API}/agent/tickets/{tid}")).json()["ticket"]
    assert after_note["status"] == "open" and after_note["first_response_at"] is None and after_note["assignee_user_id"] is None  # a note is not a response
    answer = await client.post(f"{API}/agent/tickets/{tid}/replies", json={"body": "The base case is where recursion stops."})
    ticket_after = answer.json()["ticket"]
    assert ticket_after["status"] == "assigned" and ticket_after["assignee_user_id"] == str(STAFF_A) and ticket_after["first_response_at"]
    who.student()
    detail = (await client.get(f"{API}/tickets/{tid}")).json()
    assert [m["author_role"] for m in detail["messages"]] == ["requester", "agent"]
    assert "skipped lesson" not in str(detail)
    assert [m["seq"] for m in detail["messages"]] == [1, 3]
    who.staff()
    full = (await client.get(f"{API}/agent/tickets/{tid}")).json()
    assert [m["kind"] for m in full["messages"]] == ["public", "internal", "public"]
    types = await event_types(sessionmaker)
    assert "ticket.created" in types and "ticket.assigned" in types and "ticket.replied" in types


async def test_waiting_on_student_pauses_the_clock_and_a_reply_resumes_it(client, who, sessionmaker):
    who.student()
    tid = (await open_ticket(client, category="technical"))["ticket_id"]
    who.support()
    reply = await client.post(f"{API}/agent/tickets/{tid}/replies", json={"body": "Which browser?", "then": "waiting_on_student"})
    assert reply.json()["ticket"]["status"] == "waiting_on_student"
    await backdate(sessionmaker, tid, sla_paused_at=utcnow() - timedelta(hours=2))
    who.student()
    back = await client.post(f"{API}/tickets/{tid}/replies", json={"body": "Firefox."})
    assert back.json()["ticket"]["status"] == "assigned"
    async with sessionmaker() as db:
        row = (await db.execute(select(Ticket).where(Ticket.public_id == int(tid)))).scalar_one()
        assert 7100 <= row.sla_paused_seconds <= 7300 and row.sla_paused_at is None
        assert row.resolution_due_at - row.sla_anchor_at > timedelta(minutes=4320) + timedelta(seconds=7000)  # two hours added


async def test_a_waiting_ticket_never_breaches_but_a_running_one_does(client, who, sessionmaker, settings):
    who.student()
    waiting = (await open_ticket(client, category="technical"))["ticket_id"]
    running = (await open_ticket(client, category="technical"))["ticket_id"]
    who.support()
    await client.post(f"{API}/agent/tickets/{waiting}/replies", json={"body": "Which browser?", "then": "waiting_on_student"})
    past = utcnow() - timedelta(days=30)
    await backdate(sessionmaker, waiting, resolution_due_at=past)
    await backdate(sessionmaker, running, first_response_due_at=past, resolution_due_at=past)
    async with sessionmaker() as db:
        assert await sweep_sla(db, settings) == 2  # first-response + resolution on the running ticket
    async with sessionmaker() as db:
        assert await sweep_sla(db, settings) == 0  # flagged once
    async with sessionmaker() as db:
        rows = {t.public_id: t for t in (await db.execute(select(Ticket))).scalars()}
        assert rows[int(running)].first_response_breached and rows[int(running)].resolution_breached
        assert not rows[int(waiting)].resolution_breached
    assert (await event_types(sessionmaker)).count("ticket.sla_breached") == 2
    breached = (await client.get(f"{API}/agent/tickets?breached=true")).json()["tickets"]
    assert [t["ticket_id"] for t in breached] == [running]


async def test_answered_tickets_do_not_breach_first_response(client, who, sessionmaker, settings):
    who.student()
    tid = (await open_ticket(client, category="technical"))["ticket_id"]
    who.support()
    await client.post(f"{API}/agent/tickets/{tid}/replies", json={"body": "On it."})
    await backdate(sessionmaker, tid, first_response_due_at=utcnow() - timedelta(days=1))
    async with sessionmaker() as db:
        assert await sweep_sla(db, settings) == 0


# ---------------------------------------------------------------- claim / assign / release
async def test_claim_conflicts_and_release(client, who):
    who.student()
    tid = (await open_ticket(client, category="learning"))["ticket_id"]
    who.staff()
    assert (await client.post(f"{API}/agent/tickets/{tid}/claim")).json()["ticket"]["status"] == "assigned"
    assert (await client.post(f"{API}/agent/tickets/{tid}/claim")).status_code == 200  # again: no change
    who.staff(STAFF_A2)
    conflict = await client.post(f"{API}/agent/tickets/{tid}/claim")
    assert conflict.status_code == 409 and conflict.json()["code"] == "ALREADY_ASSIGNED"
    assert (await client.post(f"{API}/agent/tickets/{tid}/release")).status_code == 403  # not theirs
    who.staff()
    released = (await client.post(f"{API}/agent/tickets/{tid}/release")).json()["ticket"]
    assert released["status"] == "open" and released["assignee_user_id"] is None
    who.staff(STAFF_A2)
    assert (await client.post(f"{API}/agent/tickets/{tid}/claim")).status_code == 200


async def test_assignment_eligibility(client, who, send_event):
    for user, role, org in ((STAFF_A, "staff", ORG_A), (STAFF_A2, "staff", ORG_A), (STAFF_B, "staff", ORG_B), (SUPPORT, "admin", None), (STUDENT, "student", ORG_A)):
        await send_event("user.created", {"user_id": str(user), "first_name": "P", "last_name": str(user), "role": role, "status": "active", "organization_id": str(org) if org else None})
    who.student()
    learning = (await open_ticket(client, category="learning"))["ticket_id"]
    technical = (await open_ticket(client, category="technical"))["ticket_id"]
    who.staff()
    assert (await client.post(f"{API}/agent/tickets/{learning}/assign", json={"assignee_user_id": str(STAFF_A2)})).status_code == 403  # staff cannot assign others
    who.head()
    ok = await client.post(f"{API}/agent/tickets/{learning}/assign", json={"assignee_user_id": str(STAFF_A2)})
    assert ok.status_code == 200 and ok.json()["ticket"]["assignee_user_id"] == str(STAFF_A2)
    for bad in (STAFF_B, SUPPORT, STUDENT, 1755000000039999):  # another institution, a platform agent, a student, a stranger
        r = await client.post(f"{API}/agent/tickets/{learning}/assign", json={"assignee_user_id": str(bad)})
        assert r.status_code == 422 and r.json()["code"] == "ASSIGNEE_NOT_ELIGIBLE", bad
    assert (await client.post(f"{API}/agent/tickets/{technical}/assign", json={"assignee_user_id": str(SUPPORT)})).status_code == 404  # head cannot see platform queue
    who.support()
    assert (await client.post(f"{API}/agent/tickets/{technical}/assign", json={"assignee_user_id": str(SUPPORT)})).status_code == 200
    assert (await client.post(f"{API}/agent/tickets/{technical}/assign", json={"assignee_user_id": str(STAFF_A)})).status_code == 422
    await send_event("user.suspended", {"user_id": str(STAFF_A2), "first_name": "P", "last_name": "x", "role": "staff", "status": "suspended", "organization_id": str(ORG_A)})
    assert (await client.post(f"{API}/agent/tickets/{learning}/assign", json={"assignee_user_id": str(STAFF_A2)})).status_code == 422  # suspended


async def test_the_assignee_list_is_exactly_who_assign_accepts(client, who, send_event):
    for user, role, org in ((STAFF_A, "staff", ORG_A), (STAFF_A2, "staff", ORG_A), (STAFF_B, "staff", ORG_B), (SUPPORT, "admin", None), (STUDENT, "student", ORG_A)):
        await send_event("user.created", {"user_id": str(user), "first_name": "P", "last_name": str(user), "role": role, "status": "active", "organization_id": str(org) if org else None})
    await send_event("user.suspended", {"user_id": str(STAFF_A2), "first_name": "P", "last_name": "x", "role": "staff", "status": "suspended", "organization_id": str(ORG_A)})
    who.student()
    learning = (await open_ticket(client, category="learning"))["ticket_id"]
    technical = (await open_ticket(client, category="technical"))["ticket_id"]
    who.staff()
    assert (await client.get(f"{API}/agent/tickets/{learning}/assignees")).status_code == 403  # staff only claim
    who.head()
    assert [p["user_id"] for p in (await client.get(f"{API}/agent/tickets/{learning}/assignees")).json()["assignees"]] == [str(STAFF_A)]
    who.support()
    assert [p["user_id"] for p in (await client.get(f"{API}/agent/tickets/{technical}/assignees")).json()["assignees"]] == [str(SUPPORT)]


# ---------------------------------------------------------------- re-routing
async def test_changing_category_reroutes_and_priority_recomputes_the_sla(client, who):
    who.student()
    ticket = await open_ticket(client, category="learning")
    tid = ticket["ticket_id"]
    who.staff()
    await client.post(f"{API}/agent/tickets/{tid}/claim")
    moved = await client.patch(f"{API}/agent/tickets/{tid}", json={"category": "technical"})
    body = moved.json()["ticket"]
    assert moved.status_code == 200 and body["queue"] == "platform_support" and body["assignee_user_id"] is None and body["status"] == "open"
    assert (await client.get(f"{API}/agent/tickets/{tid}")).status_code == 404  # no longer theirs
    who.support()
    urgent = (await client.patch(f"{API}/agent/tickets/{tid}", json={"priority": "urgent"})).json()["ticket"]
    assert urgent["first_response_due_at"] < body["first_response_due_at"]
    events = (await client.get(f"{API}/agent/tickets/{tid}/events")).json()["events"]
    assert {"created", "assigned", "recategorized", "priority_changed"} <= {e["event_type"] for e in events}


# ---------------------------------------------------------------- resolve / reopen / close / CSAT
async def test_resolve_csat_reopen_and_close(client, who, sessionmaker):
    who.student()
    tid = (await open_ticket(client, category="learning"))["ticket_id"]
    assert (await client.post(f"{API}/tickets/{tid}/csat", json={"rating": 5})).status_code == 409  # not resolved yet
    who.staff()
    resolved = (await client.post(f"{API}/agent/tickets/{tid}/replies", json={"body": "Fixed!", "then": "resolved"})).json()["ticket"]
    assert resolved["status"] == "resolved" and resolved["csat_requested_at"]
    assert (await client.post(f"{API}/agent/tickets/{tid}/resolve")).status_code == 409
    who.student()
    assert (await client.post(f"{API}/tickets/{tid}/csat", json={"rating": 6})).status_code == 422
    rated = (await client.post(f"{API}/tickets/{tid}/csat", json={"rating": 4, "comment": "quick"})).json()["ticket"]
    assert rated["csat_rating"] == 4
    again = await client.post(f"{API}/tickets/{tid}/csat", json={"rating": 5})
    assert again.status_code == 409 and again.json()["code"] == "CSAT_ALREADY_SUBMITTED"
    reopened = (await client.post(f"{API}/tickets/{tid}/replies", json={"body": "Actually it still fails"})).json()["ticket"]
    assert reopened["status"] == "assigned" and reopened["reopened_count"] == 1 and reopened["resolved_at"] is None
    who.staff()
    assert (await client.post(f"{API}/agent/tickets/{tid}/reopen")).status_code == 409  # not resolved any more
    await client.post(f"{API}/agent/tickets/{tid}/resolve")
    assert (await client.post(f"{API}/agent/tickets/{tid}/reopen")).json()["ticket"]["reopened_count"] == 2
    closed = (await client.post(f"{API}/agent/tickets/{tid}/close")).json()["ticket"]
    assert closed["status"] == "closed" and closed["closed_at"]
    who.student()
    blocked = await client.post(f"{API}/tickets/{tid}/replies", json={"body": "hello?"})
    assert blocked.status_code == 409 and blocked.json()["code"] == "TICKET_CLOSED"
    types = await event_types(sessionmaker)
    assert "ticket.csat_submitted" in types and "ticket.csat_requested" in types and "ticket.status_changed" in types


async def test_reopen_window_and_auto_close(client, who, sessionmaker, settings):
    who.student()
    tid = (await open_ticket(client, category="technical"))["ticket_id"]
    who.support()
    await client.post(f"{API}/agent/tickets/{tid}/resolve")
    await backdate(sessionmaker, tid, resolved_at=utcnow() - timedelta(days=settings.REOPEN_WINDOW_DAYS + 1))
    who.student()
    late = await client.post(f"{API}/tickets/{tid}/replies", json={"body": "still broken"})
    assert late.status_code == 409 and late.json()["code"] == "REOPEN_WINDOW_PASSED"
    assert (await client.post(f"{API}/tickets/{tid}/csat", json={"rating": 3})).status_code == 200  # rating stays open
    await backdate(sessionmaker, tid, resolved_at=utcnow() - timedelta(days=settings.AUTO_CLOSE_AFTER_DAYS + 1))
    async with sessionmaker() as db:
        assert await sweep_sla(db, settings) == 1
    who.student()
    assert (await client.get(f"{API}/tickets/{tid}")).json()["ticket"]["status"] == "closed"
    async with sessionmaker() as db:
        events = (await db.execute(select(TicketEvent).where(TicketEvent.event_type == "closed"))).scalars().all()
        assert events[0].detail["reason"] == "auto_close"


async def test_student_can_close_their_own_ticket_and_others_cannot(client, who):
    who.student()
    tid = (await open_ticket(client))["ticket_id"]
    who.student(STUDENT_2)
    assert (await client.post(f"{API}/tickets/{tid}/close")).status_code == 404
    who.student()
    assert (await client.post(f"{API}/tickets/{tid}/close")).json()["ticket"]["status"] == "closed"
    assert (await client.post(f"{API}/tickets/{tid}/close")).status_code == 200  # idempotent


# ---------------------------------------------------------------- canned replies
async def test_canned_replies_scoping_and_rendering(client, who, send_event):
    await send_event("user.created", {"user_id": str(STUDENT), "first_name": "Asha", "last_name": "Rao", "role": "student", "status": "active", "organization_id": str(ORG_A)})
    who.staff()
    org_reply = (await client.post(f"{API}/agent/canned-replies", json={"scope": "organization", "title": "Greeting", "body": "Hi {{student_first_name}}, about {{ticket_subject}}: "})).json()["canned_reply"]
    assert (await client.post(f"{API}/agent/canned-replies", json={"scope": "platform", "title": "x", "body": "y"})).status_code == 403
    who.support()
    platform = (await client.post(f"{API}/agent/canned-replies", json={"scope": "platform", "title": "Thanks", "body": "Thanks!"})).json()["canned_reply"]
    who.staff()
    titles = {r["title"] for r in (await client.get(f"{API}/agent/canned-replies")).json()["canned_replies"]}
    assert titles == {"Greeting", "Thanks"}
    who.staff(STAFF_B, ORG_B)
    assert {r["title"] for r in (await client.get(f"{API}/agent/canned-replies")).json()["canned_replies"]} == {"Thanks"}
    assert (await client.patch(f"{API}/agent/canned-replies/{org_reply['canned_reply_id']}", json={"title": "Hijack"})).status_code == 403
    assert (await client.patch(f"{API}/agent/canned-replies/{platform['canned_reply_id']}", json={"title": "Hijack"})).status_code == 403
    who.student()
    tid = (await open_ticket(client, subject="Recursion doubt"))["ticket_id"]
    who.staff()
    rendered = (await client.get(f"{API}/agent/canned-replies/{org_reply['canned_reply_id']}/render?ticket_id={tid}")).json()["rendered"]["body"]
    assert rendered == "Hi Asha, about Recursion doubt:"
    edited = await client.patch(f"{API}/agent/canned-replies/{org_reply['canned_reply_id']}", json={"active": False})
    assert edited.json()["canned_reply"]["active"] is False
    assert "Greeting" not in {r["title"] for r in (await client.get(f"{API}/agent/canned-replies")).json()["canned_replies"]}
    who.support()
    assert (await client.get(f"{API}/agent/canned-replies/{platform['canned_reply_id']}/render?ticket_id={tid}")).json()["rendered"]["body"] == "Thanks!"


# ---------------------------------------------------------------- SLA policies, summary, report
async def test_sla_policy_overrides_apply_to_new_tickets(client, who):
    who.staff()
    assert (await client.get(f"{API}/admin/sla-policies")).status_code == 403
    who.support()
    policies = (await client.get(f"{API}/admin/sla-policies")).json()["policies"]
    assert len(policies) == 12 and all(p["is_default"] for p in policies)
    bad = await client.put(f"{API}/admin/sla-policies", json={"queue": "platform_support", "priority": "normal", "first_response_minutes": 100, "resolution_minutes": 50})
    assert bad.status_code == 409
    assert (await client.put(f"{API}/admin/sla-policies", json={"queue": "platform_support", "priority": "normal", "first_response_minutes": 10, "resolution_minutes": 60})).status_code == 200
    who.student()
    ticket = await open_ticket(client, category="technical")
    created = ticket["created_at"]
    assert ticket["first_response_due_at"] and ticket["first_response_due_at"] != created
    who.support()
    mine = [p for p in (await client.get(f"{API}/admin/sla-policies")).json()["policies"] if not p["is_default"]]
    assert mine == [{"queue": "platform_support", "priority": "normal", "first_response_minutes": 10, "resolution_minutes": 60, "is_default": False}]
    reset = await client.delete(f"{API}/admin/sla-policies/platform_support/normal")
    assert all(p["is_default"] for p in reset.json()["policies"])


async def test_summary_and_report(client, who, sessionmaker):
    who.student()
    a = (await open_ticket(client, category="technical"))["ticket_id"]
    b = (await open_ticket(client, category="technical"))["ticket_id"]
    await open_ticket(client, category="billing")
    who.support()
    await client.post(f"{API}/agent/tickets/{a}/replies", json={"body": "hello", "then": "resolved"})
    await client.post(f"{API}/agent/tickets/{b}/claim")
    summary = (await client.get(f"{API}/agent/tickets/summary")).json()["queues"]
    assert summary == [{"queue": "platform_support", "open": 1, "assigned": 1, "waiting_on_student": 0, "unassigned": 1, "breached": 0, "oldest_unanswered_minutes": summary[0]["oldest_unanswered_minutes"]}]
    assert summary[0]["oldest_unanswered_minutes"] is not None
    who.student()
    await client.post(f"{API}/tickets/{a}/csat", json={"rating": 5})
    who.support()
    report = (await client.get(f"{API}/agent/reports/sla")).json()["report"]
    assert report["tickets"] == 3 and report["resolved"] == 1 and report["csat_average"] == 5.0 and report["csat_responses"] == 1
    assert report["first_response_compliance"] == 1.0 and report["avg_first_response_minutes"] is not None
    assert (await client.get(f"{API}/agent/reports/sla?start=2030-01-01T00:00:00Z&end=2029-01-01T00:00:00Z")).status_code == 422
    who.staff()
    assert (await client.get(f"{API}/agent/reports/sla")).json()["report"]["tickets"] == 0  # staff see only their own queue
    who.super_admin()
    assert (await client.get(f"{API}/agent/reports/sla")).json()["report"]["tickets"] == 3


# ---------------------------------------------------------------- internal API and consumers
async def test_internal_ticket_creation_is_idempotent_and_protected(client, internal_headers, sessionmaker):
    payload = {"requester_user_id": str(STUDENT), "organization_id": str(ORG_A), "subject": "Tutor hand-off: recursion", "description": "Summary for the agent.", "source_ref": "1755000000040001", "course_id": str(COURSE)}
    assert (await client.post(f"{API}/internal/tickets", json=payload)).status_code == 403
    assert (await client.post(f"{API}/internal/tickets", json=payload, headers={**internal_headers, "Idempotency-Key": "escalation-0001"})).status_code == 201
    first = (await client.post(f"{API}/internal/tickets", json=payload, headers={**internal_headers, "Idempotency-Key": "escalation-0001"})).json()["ticket"]
    second = (await client.post(f"{API}/internal/tickets", json=payload, headers={**internal_headers, "Idempotency-Key": "escalation-0001"})).json()["ticket"]
    assert first["ticket_id"] == second["ticket_id"] and first["queue"] == "batch_staff"
    assert (await event_types(sessionmaker)).count("ticket.created") == 1
    assert parse_public_id(first["ticket_id"])
    other = (await client.post(f"{API}/internal/tickets", json=payload, headers={**internal_headers, "Idempotency-Key": "escalation-0002"})).json()["ticket"]
    assert other["ticket_id"] != first["ticket_id"]


async def test_user_events_are_idempotent_and_keep_the_row_when_deleted(send_event, sessionmaker):
    from app.models.config import UserRef

    body = {"user_id": str(STAFF_A), "first_name": "Sam", "last_name": "Lee", "role": "staff", "status": "active", "organization_id": str(ORG_A)}
    await send_event("user.created", body, event_id="evt-1")
    await send_event("user.created", {**body, "first_name": "Ignored"}, event_id="evt-1")  # a redelivery
    async with sessionmaker() as db:
        ref = await db.get(UserRef, STAFF_A)
        assert ref.first_name == "Sam" and ref.active and ref.organization_id == ORG_A
    await send_event("user.updated", {**body, "first_name": "Samantha"})
    await send_event("user.deleted", {"user_id": str(STAFF_A)})
    await send_event("course.published", {"course_id": "1"})  # not ours
    await send_event("user.created", {"first_name": "no id"})  # malformed: ignored
    async with sessionmaker() as db:
        ref = await db.get(UserRef, STAFF_A)
        assert ref.first_name == "Samantha" and not ref.active


async def test_requester_names_show_to_agents(client, who, send_event):
    await send_event("user.created", {"user_id": str(STUDENT), "first_name": "Asha", "last_name": "Rao", "role": "student", "status": "active", "organization_id": str(ORG_A)})
    who.student()
    tid = (await open_ticket(client))["ticket_id"]
    who.staff()
    detail = (await client.get(f"{API}/agent/tickets/{tid}")).json()
    assert detail["requester_name"] == "Asha Rao" and detail["assignee_name"] is None


async def test_the_tutors_exact_handoff_payload_is_accepted(client, internal_headers, who, sessionmaker):
    """Contract with ai-tutor-service (app/services/escalation_service.py builds this payload)."""
    payload = {
        "organization_id": str(ORG_A), "requester_user_id": str(STUDENT), "subject": "Doubt on recursion", "description": "Summary Course: Python",
        "category": "billing", "source": "ai-tutor", "source_ref": "1755000000040001", "reason": "sensitive_topic", "course_id": str(COURSE),
    }
    response = await client.post(f"{API}/internal/tickets", json=payload, headers={**internal_headers, "Idempotency-Key": "1755000000040099"})
    assert response.status_code == 201 and response.json()["ticket"]["queue"] == "platform_support"
    who.support()
    tid = response.json()["ticket"]["ticket_id"]
    assert (await client.get(f"{API}/agent/tickets/{tid}")).json()["ticket"]["source"] == "ai-tutor"
    events = (await client.get(f"{API}/agent/tickets/{tid}/events")).json()["events"]
    assert events[0]["detail"] == {"source": "ai-tutor", "reason": "sensitive_topic"}
    del payload["reason"]
    payload["unexpected"] = 1
    assert (await client.post(f"{API}/internal/tickets", json=payload, headers=internal_headers)).status_code == 422


async def test_support_follows_the_persons_permissions(client, act_as):
    """A super admin can stop one student opening tickets, or take one staff member off the queue."""
    act_as(STUDENT, role="student", organization_id=ORG_A, defaults=False)
    body = {"subject": "Cannot open the lab", "description": "It says access denied", "category": "technical"}
    assert (await client.post(f"{API}/tickets", json=body)).status_code == 403
    act_as(STAFF_A, role="staff", organization_id=ORG_A, defaults=False)
    assert (await client.get(f"{API}/agent/tickets")).status_code == 403
    act_as(STAFF_A, role="staff", organization_id=ORG_A)
    assert (await client.get(f"{API}/agent/tickets")).status_code == 200


async def test_only_people_who_still_hold_the_permission_can_be_assigned(client, who, send_event, people):
    for user, role, org in ((STAFF_A, "staff", ORG_A), (STAFF_A2, "staff", ORG_A)):
        await send_event("user.created", {"user_id": str(user), "first_name": "P", "last_name": str(user), "role": role, "status": "active", "organization_id": str(org)})
    who.student()
    learning = (await open_ticket(client, category="learning"))["ticket_id"]
    people.removed.add((STAFF_A2, "support_queue.update"))  # a super admin took answering away from this one staff member
    who.head()
    listed = (await client.get(f"{API}/agent/tickets/{learning}/assignees")).json()["assignees"]
    assert [p["user_id"] for p in listed] == [str(STAFF_A)]
    refused = await client.post(f"{API}/agent/tickets/{learning}/assign", json={"assignee_user_id": str(STAFF_A2)})
    assert refused.status_code == 422 and refused.json()["code"] == "ASSIGNEE_NOT_ELIGIBLE"
    assert people.calls[-1] == {"permission": "support_queue.update", "user_ids": [str(STAFF_A2)]}

    people.down = True  # never assign on a guess
    unavailable = await client.post(f"{API}/agent/tickets/{learning}/assign", json={"assignee_user_id": str(STAFF_A)})
    assert unavailable.status_code == 502
