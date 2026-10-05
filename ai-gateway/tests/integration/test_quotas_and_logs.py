from app.providers.base import ChatResult
from tests.conftest import ORG_A, ORG_B, STAFF_A, USER


async def _completed_call(client, who, fake_chat) -> None:
    who.ai_manager()
    await client.post("/api/v1/prompts", json={"key": "tutor.explain", "owner_service": "ai-tutor-service"})
    created = await client.post("/api/v1/prompts/tutor.explain/versions", json={"template": "Explain {{topic}}.", "variables": ["topic"]})
    who.other_ai_manager()
    await client.post(f"/api/v1/prompts/tutor.explain/versions/{created.json()['version']['version']}/activate")
    fake_chat.queue_result(ChatResult(content="Recursion is self-reference.", model="claude-sonnet-5", prompt_tokens=5, completion_tokens=5, stop_reason="end_turn"))
    body = {"organization_id": str(ORG_A), "service": "ai-tutor-service", "user_id": str(USER), "prompt_key": "tutor.explain", "variables": {"topic": "recursion"}, "messages": [{"role": "user", "content": "email me at a@b.com"}]}
    response = await client.post("/api/v1/internal/completions", json=body, headers={"X-Internal-Service-Token": "test-internal-service-token-0123456789"})
    assert response.status_code == 200


async def test_get_quota_defaults_when_no_override_exists(client, who, settings):
    who.ai_manager()
    response = await client.get(f"/api/v1/orgs/{ORG_A}/quota")
    assert response.status_code == 200
    quota = response.json()["quota"]
    assert quota["is_default"] is True
    assert quota["monthly_token_limit"] == settings.DEFAULT_MONTHLY_TOKEN_LIMIT


async def test_only_an_ai_manager_can_set_quota(client, who):
    who.staff()
    response = await client.put(f"/api/v1/orgs/{ORG_A}/quota", json={"monthly_token_limit": 500, "monthly_request_limit": 10, "monthly_budget_cents": 100, "enabled": True})
    assert response.status_code == 403


async def test_set_and_read_back_a_quota_override(client, who):
    who.ai_manager()
    updated = await client.put(f"/api/v1/orgs/{ORG_A}/quota", json={"monthly_token_limit": 500, "monthly_request_limit": 10, "monthly_budget_cents": 100, "enabled": False})
    assert updated.status_code == 200
    quota = updated.json()["quota"]
    assert quota["monthly_token_limit"] == 500 and quota["enabled"] is False and quota["is_default"] is False

    fetched = (await client.get(f"/api/v1/orgs/{ORG_A}/quota")).json()["quota"]
    assert fetched["monthly_token_limit"] == 500


async def test_institution_staff_can_view_their_own_org_usage_but_not_another_orgs(client, who):
    who.staff(STAFF_A, organization_id=ORG_A)
    own = await client.get(f"/api/v1/orgs/{ORG_A}/usage")
    assert own.status_code == 200

    other = await client.get(f"/api/v1/orgs/{ORG_B}/usage")
    assert other.status_code == 403


async def test_a_student_cannot_view_org_usage(client, who):
    who.student()
    response = await client.get(f"/api/v1/orgs/{ORG_A}/usage")
    assert response.status_code == 403


async def test_usage_starts_at_zero_and_reflects_configured_limits(client, who):
    who.ai_manager()
    usage = (await client.get(f"/api/v1/orgs/{ORG_A}/usage")).json()["usage"]
    assert usage["requests_used"] == 0 and usage["period"]


async def test_logs_list_is_ai_manager_only(client, who):
    who.staff()
    response = await client.get("/api/v1/logs")
    assert response.status_code == 403


async def test_logs_list_returns_an_empty_page_with_no_calls_yet(client, who):
    who.ai_manager()
    response = await client.get("/api/v1/logs")
    assert response.status_code == 200
    assert response.json()["logs"] == []


async def test_a_completed_call_appears_in_the_log_with_pii_already_redacted(client, who, fake_chat):
    await _completed_call(client, who, fake_chat)
    who.ai_manager()
    logs = (await client.get("/api/v1/logs")).json()["logs"]
    assert len(logs) == 1
    entry = logs[0]
    assert entry["status"] == "ok" and entry["provider"] == "anthropic" and entry["prompt_key"] == "tutor.explain"
    assert "a@b.com" not in str(entry["request_redacted"])
    assert entry["response_preview"] == "Recursion is self-reference."


async def test_logs_can_be_filtered_by_organization_and_status(client, who, fake_chat):
    await _completed_call(client, who, fake_chat)
    who.ai_manager()
    matching = (await client.get("/api/v1/logs", params={"organization_id": str(ORG_A), "status": "ok"})).json()["logs"]
    assert len(matching) == 1
    other_org = (await client.get("/api/v1/logs", params={"organization_id": str(ORG_B)})).json()["logs"]
    assert other_org == []
    other_status = (await client.get("/api/v1/logs", params={"status": "blocked"})).json()["logs"]
    assert other_status == []


async def test_get_and_set_model_routes(client, who, settings):
    who.ai_manager()
    routes = (await client.get("/api/v1/models")).json()["models"]
    assert routes["chat"][0]["provider"] == "anthropic" and routes["chat"][0]["model"] == settings.ANTHROPIC_DEFAULT_MODEL

    updated = await client.patch("/api/v1/models/chat", json={"providers": [{"provider": "anthropic", "model": "claude-opus-5"}]})
    assert updated.status_code == 200
    assert updated.json()["providers"] == [{"provider": "anthropic", "model": "claude-opus-5"}]

    fetched = (await client.get("/api/v1/models")).json()["models"]
    assert fetched["chat"] == [{"provider": "anthropic", "model": "claude-opus-5"}]


async def test_setting_an_unknown_provider_for_a_capability_is_rejected(client, who):
    who.ai_manager()
    response = await client.patch("/api/v1/models/embedding", json={"providers": [{"provider": "anthropic", "model": "claude-sonnet-5"}]})
    assert response.status_code == 422
    assert response.json()["code"] == "UNKNOWN_PROVIDER"


async def test_setting_an_empty_route_is_rejected(client, who):
    who.ai_manager()
    response = await client.patch("/api/v1/models/chat", json={"providers": []})
    assert response.status_code == 422
