"""Interview plans: who may write which kind, validation of rounds and the rubric, and the draft -> publish -> new version lifecycle."""

from tests.conftest import API, EMPLOYER, EMPLOYER_2, RECRUITER_2, create_published_plan, plan_body, round_body


async def test_a_careers_manager_creates_a_mock_plan(client, who):
    who.manager()
    created = await client.post(f"{API}/interview-plans", json=plan_body(kind="mock"))
    assert created.status_code == 201, created.text
    plan = created.json()["plan"]
    assert plan["status"] == "draft" and plan["owner_org_id"] is None and plan["version"] == 1


async def test_a_recruiter_cannot_create_a_mock_plan(client, who):
    who.recruiter()
    response = await client.post(f"{API}/interview-plans", json=plan_body(kind="mock"))
    assert response.status_code == 403


async def test_a_student_cannot_write_plans(client, who):
    who.student()
    response = await client.post(f"{API}/interview-plans", json=plan_body(kind="mock"))
    assert response.status_code == 403


async def test_a_recruiter_creates_a_screening_plan_owned_by_their_employer(client, who):
    who.recruiter()
    created = await client.post(f"{API}/interview-plans", json=plan_body(kind="screening"))
    assert created.status_code == 201, created.text
    assert created.json()["plan"]["owner_org_id"] == str(EMPLOYER)


async def test_rounds_must_add_up_to_no_more_than_the_duration(client, who):
    who.manager()
    body = plan_body(kind="mock", duration_minutes=10, rounds=[round_body(type_="intro", minutes=5), round_body(type_="technical", minutes=10)])
    response = await client.post(f"{API}/interview-plans", json=body)
    assert response.status_code == 422
    assert response.json()["details"][0]["code"] == "TOO_LONG"


async def test_a_system_design_round_needs_a_senior_plan(client, who):
    who.manager()
    body = plan_body(kind="mock", difficulty="medium", rounds=[round_body(type_="system_design", minutes=10)])
    response = await client.post(f"{API}/interview-plans", json=body)
    assert response.status_code == 422
    assert response.json()["details"][0]["code"] == "SENIOR_ONLY"


async def test_a_coding_round_needs_languages_and_is_scored_on_code_quality(client, who):
    who.manager()
    body = plan_body(kind="mock", rounds=[round_body(type_="coding", minutes=10)])
    response = await client.post(f"{API}/interview-plans", json=body)
    assert response.status_code == 422
    assert response.json()["details"][0]["code"] == "REQUIRED"


async def test_criteria_weights_must_sum_to_one(client, who):
    who.manager()
    body = plan_body(kind="mock", criteria_weights={"communication": 0.9})
    response = await client.post(f"{API}/interview-plans", json=body)
    assert response.status_code == 422


async def test_publish_freezes_the_plan_and_a_new_version_starts_a_fresh_draft(client, who):
    plan_id = await create_published_plan(client, who, kind="mock")
    who.manager()
    locked = await client.patch(f"{API}/interview-plans/{plan_id}", json={"title": "New title"})
    assert locked.status_code == 409

    versioned = await client.post(f"{API}/interview-plans/{plan_id}/versions")
    assert versioned.status_code == 201, versioned.text
    draft = versioned.json()["plan"]
    assert draft["status"] == "draft" and draft["version"] == 2 and draft["family_id"] == plan_id

    again = await client.post(f"{API}/interview-plans/{plan_id}/versions")
    assert again.status_code == 409 and again.json()["code"] == "DRAFT_EXISTS"


async def test_retiring_a_draft_is_refused(client, who):
    who.manager()
    created = await client.post(f"{API}/interview-plans", json=plan_body(kind="mock"))
    plan_id = created.json()["plan"]["plan_id"]
    response = await client.post(f"{API}/interview-plans/{plan_id}/retire")
    assert response.status_code == 409 and response.json()["code"] == "PLAN_NOT_PUBLISHED"


async def test_a_company_cannot_see_or_edit_another_companys_plan(client, who):
    who.recruiter()
    created = await client.post(f"{API}/interview-plans", json=plan_body(kind="screening"))
    plan_id = created.json()["plan"]["plan_id"]

    who.recruiter(RECRUITER_2, EMPLOYER_2)
    hidden = await client.get(f"{API}/interview-plans/{plan_id}")
    assert hidden.status_code == 404


async def test_students_list_only_published_mock_plans(client, who):
    who.manager()
    draft = await client.post(f"{API}/interview-plans", json=plan_body(kind="mock", title="Still a draft"))
    published_id = await create_published_plan(client, who, kind="mock", title="Ready for practice")

    who.student()
    listed = await client.get(f"{API}/student/mock-plans")
    assert listed.status_code == 200
    ids = {p["plan_id"] for p in listed.json()["plans"]}
    assert published_id in ids
    assert draft.json()["plan"]["plan_id"] not in ids
