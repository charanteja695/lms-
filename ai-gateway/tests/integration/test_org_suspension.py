"""app/events/consumers/handlers.py: institution.suspended/activated block and unblock AI spend for that org."""

from app.providers.base import ChatResult
from tests.conftest import ORG_A, ORG_B, USER


async def _make_prompt(client, who) -> None:
    who.ai_manager()
    await client.post("/api/v1/prompts", json={"key": "tutor.explain", "owner_service": "ai-tutor-service"})
    created = await client.post("/api/v1/prompts/tutor.explain/versions", json={"template": "Explain {{topic}}.", "variables": ["topic"]})
    who.other_ai_manager()
    await client.post(f"/api/v1/prompts/tutor.explain/versions/{created.json()['version']['version']}/activate")


def _body(**overrides):
    base = {"organization_id": str(ORG_A), "service": "ai-tutor-service", "user_id": str(USER), "prompt_key": "tutor.explain", "variables": {"topic": "recursion"}, "messages": [{"role": "user", "content": "go"}]}
    base.update(overrides)
    return base


async def test_a_suspended_org_cannot_spend(client, who, send_event, internal_headers):
    await _make_prompt(client, who)
    await send_event("institution.suspended", {"organization_id": str(ORG_A)})

    response = await client.post("/api/v1/internal/completions", json=_body(), headers=internal_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "ORG_SUSPENDED"


async def test_reactivating_an_org_restores_access(client, who, send_event, fake_chat, internal_headers):
    await _make_prompt(client, who)
    await send_event("institution.suspended", {"organization_id": str(ORG_A)})
    await send_event("institution.activated", {"organization_id": str(ORG_A)})

    fake_chat.queue_result(ChatResult(content="ok", model="claude-sonnet-5", prompt_tokens=1, completion_tokens=1, stop_reason="end_turn"))
    response = await client.post("/api/v1/internal/completions", json=_body(), headers=internal_headers)
    assert response.status_code == 200


async def test_suspension_is_scoped_to_the_org_it_names(client, who, send_event, fake_chat, internal_headers):
    await _make_prompt(client, who)
    await send_event("institution.suspended", {"organization_id": str(ORG_B)})

    fake_chat.queue_result(ChatResult(content="ok", model="claude-sonnet-5", prompt_tokens=1, completion_tokens=1, stop_reason="end_turn"))
    response = await client.post("/api/v1/internal/completions", json=_body(), headers=internal_headers)  # ORG_A, unaffected
    assert response.status_code == 200


async def test_a_redelivered_suspension_event_is_applied_at_most_once(client, who, send_event, internal_headers):
    """Not a behavioural difference here (setting suspended=True twice is idempotent either way), but exercises
    the processed_events de-duplication path (see app/events/consumers/router.py)."""
    await _make_prompt(client, who)
    await send_event("institution.suspended", {"organization_id": str(ORG_A)}, event_id="evt-fixed-1")
    await send_event("institution.suspended", {"organization_id": str(ORG_A)}, event_id="evt-fixed-1")

    response = await client.post("/api/v1/internal/completions", json=_body(), headers=internal_headers)
    assert response.status_code == 403
