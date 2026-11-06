"""An agent reads the tutor conversation behind a hand-off ticket (fetched from ai-tutor-service with the internal token)."""

import httpx

from app.api.deps import get_tutor_client
from app.clients.tutor import TutorClient
from tests.conftest import COURSE, ORG_A, ORG_B, STUDENT, open_ticket

API = "/api/v1"
CONVERSATION = "1755000000040001"
TRANSCRIPT = {
    "conversation": {
        "conversation_id": CONVERSATION, "mode": "learning", "course_id": str(COURSE), "title": "Recursion", "status": "escalated",
        "message_count": 2, "last_message_at": None, "created_at": "2026-10-01T10:00:00Z",
        "messages": [
            {"message_id": "11", "role": "user", "kind": "question", "content": "What is a base case?", "created_at": "2026-10-01T10:00:00Z"},
            {"message_id": "12", "role": "assistant", "kind": "answer", "content": "The condition that stops recursion.", "created_at": "2026-10-01T10:00:01Z"},
        ],
    }
}


def tutor_answering(app, settings, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    app.dependency_overrides[get_tutor_client] = lambda: TutorClient(settings, transport=httpx.MockTransport(respond))
    return seen


async def hand_off(client, internal_headers) -> str:
    payload = {"requester_user_id": str(STUDENT), "organization_id": str(ORG_A), "subject": "Tutor hand-off", "description": "Summary.", "source_ref": CONVERSATION, "course_id": str(COURSE)}
    response = await client.post(f"{API}/internal/tickets", json=payload, headers={**internal_headers, "Idempotency-Key": "esc-transcript-1"})
    return response.json()["ticket"]["ticket_id"]


async def test_an_agent_reads_the_tutor_transcript_of_a_hand_off(app, client, who, settings, internal_headers):
    ticket_id = await hand_off(client, internal_headers)
    seen = tutor_answering(app, settings, lambda request: httpx.Response(200, json=TRANSCRIPT))
    who.staff()
    detail = (await client.get(f"{API}/agent/tickets/{ticket_id}")).json()["ticket"]
    assert detail["source"] == "ai-tutor" and detail["source_ref"] == CONVERSATION
    transcript = (await client.get(f"{API}/agent/tickets/{ticket_id}/transcript")).json()["transcript"]
    assert [m["message_id"] for m in transcript["messages"]] == ["11", "12"] and transcript["title"] == "Recursion"
    assert seen[0].url.path == f"/api/v1/internal/conversations/{CONVERSATION}"
    assert seen[0].headers["X-Internal-Service-Token"] == settings.INTERNAL_SERVICE_TOKEN.get_secret_value()


async def test_only_agents_of_the_queue_see_it_and_only_for_tutor_tickets(app, client, who, settings, internal_headers):
    ticket_id = await hand_off(client, internal_headers)
    seen = tutor_answering(app, settings, lambda request: httpx.Response(200, json=TRANSCRIPT))
    who.staff(organization_id=ORG_B)
    assert (await client.get(f"{API}/agent/tickets/{ticket_id}/transcript")).status_code == 404  # another institution's queue
    who.student()
    assert (await client.get(f"{API}/agent/tickets/{ticket_id}/transcript")).status_code == 403
    portal = (await open_ticket(client))["ticket_id"]
    who.support()
    missing = await client.get(f"{API}/agent/tickets/{portal}/transcript")
    assert missing.status_code == 404 and missing.json()["code"] == "NO_TRANSCRIPT"
    assert seen == []  # ai-tutor is never asked unless the agent may see a tutor ticket


async def test_a_deleted_conversation_and_a_silent_tutor_are_reported(app, client, who, settings, internal_headers):
    ticket_id = await hand_off(client, internal_headers)
    who.support()
    tutor_answering(app, settings, lambda request: httpx.Response(404, json={"code": "CONVERSATION_NOT_FOUND"}))
    gone = await client.get(f"{API}/agent/tickets/{ticket_id}/transcript")
    assert gone.status_code == 404 and gone.json()["code"] == "NO_TRANSCRIPT"
    tutor_answering(app, settings, lambda request: httpx.Response(503))
    down = await client.get(f"{API}/agent/tickets/{ticket_id}/transcript")
    assert down.status_code == 502 and down.json()["code"] == "UPSTREAM_UNAVAILABLE"
