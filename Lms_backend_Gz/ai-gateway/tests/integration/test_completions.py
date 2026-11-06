"""End-to-end through the HTTP API, against the fake providers registered in tests/conftest.py."""

import json

from app.providers.base import ChatChunk, ChatResult, ProviderCallError
from tests.conftest import ORG_A, USER


async def _make_prompt(client, who, *, key: str = "tutor.explain", template: str = "Explain {{topic}} to a beginner.", variables=("topic",), allowed_tools=()) -> None:
    who.ai_manager()
    await client.post("/api/v1/prompts", json={"key": key, "owner_service": "ai-tutor-service"})
    created = await client.post(f"/api/v1/prompts/{key}/versions", json={"template": template, "variables": list(variables), "allowed_tools": list(allowed_tools)})
    version_number = created.json()["version"]["version"]
    who.other_ai_manager()  # activator must differ from the author (see app/services/prompt_service.py)
    await client.post(f"/api/v1/prompts/{key}/versions/{version_number}/activate")


def _body(**overrides):
    base = {
        "organization_id": str(ORG_A), "service": "ai-tutor-service", "user_id": str(USER), "prompt_key": "tutor.explain",
        "variables": {"topic": "recursion"}, "messages": [{"role": "user", "content": "Can you explain it with an example?"}],
    }
    base.update(overrides)
    return base


async def test_a_completion_calls_the_provider_and_returns_content(client, who, fake_chat):
    await _make_prompt(client, who)
    fake_chat.queue_result(ChatResult(content="Recursion is when a function calls itself.", model="claude-sonnet-5-5", prompt_tokens=20, completion_tokens=10, stop_reason="end_turn"))

    response = await client.post("/api/v1/internal/completions", json=_body(), headers={"X-Internal-Service-Token": "test-internal-service-token-0123456789"})
    assert response.status_code == 200
    completion = response.json()["completion"]
    assert completion["status"] == "ok"
    assert completion["content"] == "Recursion is when a function calls itself."
    assert completion["provider"] == "anthropic" and completion["prompt_tokens"] == 20 and completion["completion_tokens"] == 10
    assert completion["prompt_version"] == 1  # callers that log decisions for audit record which prompt version answered
    assert len(fake_chat.calls) == 1
    assert fake_chat.calls[0].system == "Explain recursion to a beginner."


async def test_without_the_internal_token_the_call_is_refused(client, who):
    await _make_prompt(client, who)
    response = await client.post("/api/v1/internal/completions", json=_body())
    assert response.status_code == 403


async def test_a_missing_template_variable_is_a_422(client, who, internal_headers):
    await _make_prompt(client, who)
    response = await client.post("/api/v1/internal/completions", json=_body(variables={}), headers=internal_headers)
    assert response.status_code == 422
    assert response.json()["code"] == "MISSING_TEMPLATE_VARIABLE"


async def test_an_unknown_prompt_key_is_a_404(client, who, internal_headers):
    response = await client.post("/api/v1/internal/completions", json=_body(prompt_key="does.not.exist"), headers=internal_headers)
    assert response.status_code == 404


async def test_pii_in_a_message_is_redacted_before_reaching_the_provider(client, who, fake_chat, internal_headers):
    await _make_prompt(client, who)
    response = await client.post(
        "/api/v1/internal/completions", json=_body(messages=[{"role": "user", "content": "Email me the answer at aarav@example.com"}]), headers=internal_headers
    )
    assert response.status_code == 200
    assert "aarav@example.com" not in fake_chat.calls[0].messages[0].content
    assert "pii:email" in response.json()["completion"]["guardrail_flags"]


async def test_a_moderated_phrase_blocks_the_call_without_reaching_the_provider(client, who, fake_chat, settings, internal_headers):
    settings.MODERATION_BLOCKLIST.append("how to pick a lock")
    await _make_prompt(client, who)
    response = await client.post("/api/v1/internal/completions", json=_body(messages=[{"role": "user", "content": "how to pick a lock"}]), headers=internal_headers)
    assert response.status_code == 200
    completion = response.json()["completion"]
    assert completion["status"] == "blocked" and completion["content"] == ""
    assert "moderation" in completion["guardrail_flags"]
    assert fake_chat.calls == []


async def test_a_disallowed_tool_is_rejected(client, who, internal_headers):
    await _make_prompt(client, who, allowed_tools=["lookup_enrolment_status"])
    response = await client.post("/api/v1/internal/completions", json=_body(tools=[{"name": "delete_everything"}]), headers=internal_headers)
    assert response.status_code == 422
    assert response.json()["code"] == "TOOL_NOT_ALLOWED"


async def test_an_allowed_tool_passes_through(client, who, fake_chat, internal_headers):
    await _make_prompt(client, who, allowed_tools=["lookup_enrolment_status"])
    response = await client.post("/api/v1/internal/completions", json=_body(tools=[{"name": "lookup_enrolment_status"}]), headers=internal_headers)
    assert response.status_code == 200
    assert fake_chat.calls[0].tools == [{"name": "lookup_enrolment_status"}]


async def test_the_org_quota_is_enforced(client, who, settings, internal_headers):
    settings.DEFAULT_MONTHLY_REQUEST_LIMIT = 1
    await _make_prompt(client, who)
    first = await client.post("/api/v1/internal/completions", json=_body(), headers=internal_headers)
    assert first.status_code == 200
    second = await client.post("/api/v1/internal/completions", json=_body(), headers=internal_headers)
    assert second.status_code == 429
    assert second.json()["code"] == "REQUEST_QUOTA_EXCEEDED"


async def test_a_provider_failure_refunds_the_reservation_and_returns_502(client, who, fake_chat, internal_headers):
    await _make_prompt(client, who)
    fake_chat.queue_error(ProviderCallError("boom"))
    response = await client.post("/api/v1/internal/completions", json=_body(), headers=internal_headers)
    assert response.status_code == 502
    assert response.json()["code"] == "PROVIDER_UNAVAILABLE"

    who.ai_manager()
    usage = (await client.get(f"/api/v1/orgs/{ORG_A}/usage")).json()["usage"]
    # requests_used still counts the attempt (it reached a provider and failed); the token estimate is refunded
    # in full since nothing was actually generated (see QuotaService.refund).
    assert usage["requests_used"] == 1 and usage["completion_tokens_used"] == 0


async def test_an_idempotency_key_replays_the_cached_result_without_calling_the_provider_again(client, who, fake_chat, internal_headers):
    await _make_prompt(client, who)
    headers = {**internal_headers, "Idempotency-Key": "retry-12345678"}
    first = await client.post("/api/v1/internal/completions", json=_body(), headers=headers)
    second = await client.post("/api/v1/internal/completions", json=_body(), headers=headers)
    assert first.json()["completion"]["call_id"] == second.json()["completion"]["call_id"]
    assert len(fake_chat.calls) == 1


async def test_an_idempotency_key_reused_with_a_different_body_conflicts(client, who, internal_headers):
    await _make_prompt(client, who)
    headers = {**internal_headers, "Idempotency-Key": "retry-87654321"}
    await client.post("/api/v1/internal/completions", json=_body(), headers=headers)
    response = await client.post("/api/v1/internal/completions", json=_body(variables={"topic": "iteration"}), headers=headers)
    assert response.status_code == 409


async def test_streaming_yields_deltas_then_a_usage_line(client, who, fake_chat, internal_headers):
    await _make_prompt(client, who)
    fake_chat.queue_stream([ChatChunk(delta_text="Hel"), ChatChunk(delta_text="lo"), ChatChunk(delta_text="", done=True, stop_reason="end_turn", prompt_tokens=8, completion_tokens=2)])
    async with client.stream("POST", "/api/v1/internal/completions", json=_body(stream=True), headers=internal_headers) as response:
        assert response.status_code == 200
        lines = [line async for line in response.aiter_lines() if line]

    events = [json.loads(line) for line in lines]
    assert [e["text"] for e in events if e["type"] == "delta"] == ["Hel", "lo"]
    usage_event = events[-1]
    assert usage_event["type"] == "usage" and usage_event["prompt_tokens"] == 8 and usage_event["completion_tokens"] == 2


async def test_a_moderated_streaming_request_returns_a_normal_json_response_not_a_stream(client, who, settings, internal_headers):
    settings.MODERATION_BLOCKLIST.append("how to pick a lock")
    await _make_prompt(client, who)
    response = await client.post("/api/v1/internal/completions", json=_body(stream=True, messages=[{"role": "user", "content": "how to pick a lock"}]), headers=internal_headers)
    assert response.status_code == 200
    assert response.json()["completion"]["status"] == "blocked"
