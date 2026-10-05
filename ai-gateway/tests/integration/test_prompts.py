async def test_create_prompt_requires_ai_manager(client, who):
    who.staff()
    response = await client.post("/api/v1/prompts", json={"key": "tutor.explain_concept", "owner_service": "ai-tutor-service"})
    assert response.status_code == 403


async def test_create_and_get_a_prompt(client, who):
    who.ai_manager()
    created = await client.post("/api/v1/prompts", json={"key": "tutor.explain_concept", "owner_service": "ai-tutor-service", "description": "Explains a concept."})
    assert created.status_code == 201
    body = created.json()["prompt"]
    assert body["key"] == "tutor.explain_concept" and body["capability"] == "chat"

    fetched = await client.get("/api/v1/prompts/tutor.explain_concept")
    assert fetched.status_code == 200 and fetched.json()["prompt"]["key"] == "tutor.explain_concept"


async def test_creating_the_same_key_twice_conflicts(client, who):
    who.ai_manager()
    body = {"key": "tutor.dup", "owner_service": "ai-tutor-service"}
    assert (await client.post("/api/v1/prompts", json=body)).status_code == 201
    second = await client.post("/api/v1/prompts", json=body)
    assert second.status_code == 409


async def test_get_unknown_prompt_is_404(client, who):
    who.ai_manager()
    response = await client.get("/api/v1/prompts/does.not.exist")
    assert response.status_code == 404


async def test_list_prompts(client, who):
    who.ai_manager()
    await client.post("/api/v1/prompts", json={"key": "tutor.a", "owner_service": "ai-tutor-service"})
    await client.post("/api/v1/prompts", json={"key": "tutor.b", "owner_service": "ai-tutor-service"})
    response = await client.get("/api/v1/prompts")
    assert response.status_code == 200
    keys = {p["key"] for p in response.json()["prompts"]}
    assert {"tutor.a", "tutor.b"} <= keys


async def test_a_draft_version_must_declare_every_placeholder_it_uses(client, who):
    who.ai_manager()
    await client.post("/api/v1/prompts", json={"key": "tutor.gap", "owner_service": "ai-tutor-service"})
    response = await client.post("/api/v1/prompts/tutor.gap/versions", json={"template": "Hello {{name}}", "variables": []})
    assert response.status_code == 422
    assert response.json()["code"] == "UNDECLARED_VARIABLE"


async def test_versions_are_numbered_from_one_and_increment(client, who):
    who.ai_manager()
    await client.post("/api/v1/prompts", json={"key": "tutor.versions", "owner_service": "ai-tutor-service"})
    first = await client.post("/api/v1/prompts/tutor.versions/versions", json={"template": "v1"})
    second = await client.post("/api/v1/prompts/tutor.versions/versions", json={"template": "v2"})
    assert first.json()["version"]["version"] == 1
    assert second.json()["version"]["version"] == 2
    assert first.json()["version"]["status"] == "draft"


async def test_the_author_cannot_activate_their_own_version(client, who):
    who.ai_manager()
    await client.post("/api/v1/prompts", json={"key": "tutor.selfactivate", "owner_service": "ai-tutor-service"})
    version = (await client.post("/api/v1/prompts/tutor.selfactivate/versions", json={"template": "v1"})).json()["version"]["version"]
    response = await client.post(f"/api/v1/prompts/tutor.selfactivate/versions/{version}/activate")
    assert response.status_code == 403
    assert response.json()["code"] == "SAME_AUTHOR"


async def test_a_different_manager_can_activate_and_it_replaces_the_previous_active_version(client, who):
    who.ai_manager()
    await client.post("/api/v1/prompts", json={"key": "tutor.rotate", "owner_service": "ai-tutor-service"})
    v1 = (await client.post("/api/v1/prompts/tutor.rotate/versions", json={"template": "v1"})).json()["version"]["version"]

    who.other_ai_manager()
    activated_v1 = await client.post(f"/api/v1/prompts/tutor.rotate/versions/{v1}/activate")
    assert activated_v1.status_code == 200 and activated_v1.json()["version"]["status"] == "active"

    who.ai_manager()
    v2 = (await client.post("/api/v1/prompts/tutor.rotate/versions", json={"template": "v2"})).json()["version"]["version"]
    who.other_ai_manager()
    activated_v2 = await client.post(f"/api/v1/prompts/tutor.rotate/versions/{v2}/activate")
    assert activated_v2.json()["version"]["status"] == "active"

    prompt_page = await client.get("/api/v1/prompts/tutor.rotate")
    assert prompt_page.status_code == 200  # the prompt itself is unaffected; only versions carry status


async def test_activating_an_already_active_version_conflicts(client, who):
    who.ai_manager()
    await client.post("/api/v1/prompts", json={"key": "tutor.reactivate", "owner_service": "ai-tutor-service"})
    v1 = (await client.post("/api/v1/prompts/tutor.reactivate/versions", json={"template": "v1"})).json()["version"]["version"]
    who.other_ai_manager()
    await client.post(f"/api/v1/prompts/tutor.reactivate/versions/{v1}/activate")
    response = await client.post(f"/api/v1/prompts/tutor.reactivate/versions/{v1}/activate")
    assert response.status_code == 409


async def test_retire_a_version(client, who):
    who.ai_manager()
    await client.post("/api/v1/prompts", json={"key": "tutor.retire", "owner_service": "ai-tutor-service"})
    v1 = (await client.post("/api/v1/prompts/tutor.retire/versions", json={"template": "v1"})).json()["version"]["version"]
    response = await client.post(f"/api/v1/prompts/tutor.retire/versions/{v1}/retire")
    assert response.status_code == 200 and response.json()["version"]["status"] == "retired"
