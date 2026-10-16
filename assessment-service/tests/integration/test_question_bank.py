from tests.conftest import EMPLOYER, ORG_A, RECRUITER, STAFF_A, mcq, subjective, true_false


async def test_author_creates_a_draft_question_with_tags(client, who):
    who.author()
    response = await client.post(
        "/api/v1/questions", json=mcq(difficulty=2, bloom="apply", skills=["JavaScript"], topics=["Arrays"], tags=["Loops", "loops"], default_marks=2)
    )
    assert response.status_code == 201, response.text
    question = response.json()["question"]
    assert question["current"] is None and question["working"]["status"] == "draft"
    assert question["working"]["skills"] == ["javascript"]  # tags are normalised, duplicates merged
    assert question["working"]["tags"] == ["loops"]
    assert question["working"]["default_marks"] == 2 and question["working"]["difficulty"] == 2


async def test_malformed_content_is_refused_with_field_details(client, who):
    who.author()
    response = await client.post("/api/v1/questions", json=mcq(correct="z"))
    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "answer_key.correct"


async def test_review_lifecycle_publishes_a_version_and_needs_a_second_pair_of_eyes(client, who):
    who.author()
    question_id = (await client.post("/api/v1/questions", json=mcq())).json()["question"]["question_id"]
    assert (await client.post(f"/api/v1/questions/{question_id}/submit")).status_code == 200

    approve_own = await client.post(f"/api/v1/questions/{question_id}/approve", json={})
    assert approve_own.status_code == 403  # the author has no review scope

    who.reviewer()
    approved = await client.post(f"/api/v1/questions/{question_id}/approve", json={"note": "Good"})
    assert approved.status_code == 200
    question = approved.json()["question"]
    assert question["current_version_no"] == 1 and question["current"]["status"] == "published"
    assert question["working"] is None


async def test_an_author_with_review_rights_cannot_approve_their_own_work_but_super_admin_can(client, who, act_as):
    act_as(AUTHOR_BOTH := 1755000000007190, role="admin", organization_id=None, scopes=("content.author", "content.review"))
    question_id = (await client.post("/api/v1/questions", json=mcq())).json()["question"]["question_id"]
    await client.post(f"/api/v1/questions/{question_id}/submit")
    refused = await client.post(f"/api/v1/questions/{question_id}/approve", json={})
    assert refused.status_code == 403 and refused.json()["code"] == "SELF_REVIEW_NOT_ALLOWED"
    who.super_admin()
    assert (await client.post(f"/api/v1/questions/{question_id}/approve", json={})).status_code == 200
    assert AUTHOR_BOTH


async def test_rejecting_sends_it_back_with_the_note_and_it_can_be_fixed_and_resubmitted(client, who):
    who.author()
    question_id = (await client.post("/api/v1/questions", json=mcq())).json()["question"]["question_id"]
    await client.post(f"/api/v1/questions/{question_id}/submit")
    who.reviewer()
    rejected = await client.post(f"/api/v1/questions/{question_id}/reject", json={"note": "Option B is ambiguous"})
    assert rejected.json()["question"]["working"]["review_note"] == "Option B is ambiguous"
    who.author()
    assert (await client.patch(f"/api/v1/questions/{question_id}", json={"text": "Clearer wording"})).status_code == 200
    assert (await client.post(f"/api/v1/questions/{question_id}/submit")).status_code == 200


async def test_a_question_in_review_cannot_be_edited(client, who):
    who.author()
    question_id = (await client.post("/api/v1/questions", json=mcq())).json()["question"]["question_id"]
    await client.post(f"/api/v1/questions/{question_id}/submit")
    response = await client.patch(f"/api/v1/questions/{question_id}", json={"text": "Sneaky"})
    assert response.status_code == 409 and response.json()["code"] == "VERSION_IN_REVIEW"


async def test_editing_a_published_question_opens_a_new_version_and_the_live_one_keeps_serving(client, who, make_question):
    question_id = await make_question(mcq(text="Original"))
    who.author()
    edited = await client.patch(f"/api/v1/questions/{question_id}", json={"text": "Edited", "difficulty": 5})
    question = edited.json()["question"]
    assert question["current"]["text"] == "Original" and question["current_version_no"] == 1
    assert question["working"]["text"] == "Edited" and question["working"]["version_no"] == 2

    await client.post(f"/api/v1/questions/{question_id}/submit")
    who.reviewer()
    approved = (await client.post(f"/api/v1/questions/{question_id}/approve", json={})).json()["question"]
    assert approved["current_version_no"] == 2 and approved["current"]["text"] == "Edited"
    versions = (await client.get(f"/api/v1/questions/{question_id}/versions")).json()["versions"]
    assert [(v["version_no"], v["status"]) for v in versions] == [(2, "published"), (1, "superseded")]


async def test_an_unpublished_edit_can_be_discarded(client, who, make_question):
    question_id = await make_question()
    who.author()
    await client.patch(f"/api/v1/questions/{question_id}", json={"text": "Edited"})
    discarded = await client.delete(f"/api/v1/questions/{question_id}/draft")
    assert discarded.status_code == 200 and discarded.json()["question"]["working"] is None
    assert discarded.json()["question"]["latest_version_no"] == 1


async def test_list_filters_by_type_difficulty_tag_and_search(client, who, make_question):
    await make_question(mcq(text="Sorting algorithms", difficulty=4, skills=["dsa"]))
    await make_question(true_false(difficulty=1, topics=["basics"]))
    who.author()
    everything = (await client.get("/api/v1/questions")).json()
    assert everything["page_context"]["total_records"] == 2

    hard = (await client.get("/api/v1/questions", params={"difficulty_min": 3})).json()["questions"]
    assert [q["text"] for q in hard] == ["Sorting algorithms"]
    by_skill = (await client.get("/api/v1/questions", params={"skill": "DSA"})).json()["questions"]
    assert len(by_skill) == 1 and by_skill[0]["question_type"] == "mcq_single"
    by_type = (await client.get("/api/v1/questions", params={"question_type": "true_false"})).json()["questions"]
    assert len(by_type) == 1
    searched = (await client.get("/api/v1/questions", params={"search": "sort"})).json()["questions"]
    assert len(searched) == 1


async def test_bulk_import_reports_each_question_on_its_own(client, who):
    who.author()
    good, bad = mcq(), mcq(correct="nope")
    response = await client.post("/api/v1/questions/bulk", json={"questions": [good, bad, true_false()]}, headers={"Idempotency-Key": "import-0001-abc"})
    assert response.status_code == 201
    body = response.json()
    assert (body["created"], body["failed"]) == (2, 1)
    assert body["results"][1]["error"] == "INVALID_DATA" and body["results"][1]["details"][0]["field"] == "answer_key.correct"
    again = await client.post("/api/v1/questions/bulk", json={"questions": [good, bad, true_false()]}, headers={"Idempotency-Key": "import-0001-abc"})
    assert again.status_code == 409  # the same import is not applied twice


async def test_create_is_idempotent_for_the_same_key(client, who):
    who.author()
    headers = {"Idempotency-Key": "create-q-0001"}
    first = await client.post("/api/v1/questions", json=mcq(), headers=headers)
    second = await client.post("/api/v1/questions", json=mcq(), headers=headers)
    assert first.json()["question"]["question_id"] == second.json()["question"]["question_id"]
    assert (await client.get("/api/v1/questions")).json()["page_context"]["total_records"] == 1
    different = await client.post("/api/v1/questions", json=mcq(text="Other"), headers=headers)
    assert different.status_code == 409 and different.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_retire_and_restore(client, who, make_question):
    question_id = await make_question()
    who.reviewer()
    retired = await client.post(f"/api/v1/questions/{question_id}/retire")
    assert retired.json()["question"]["status"] == "retired"
    assert (await client.post(f"/api/v1/questions/{question_id}/restore")).json()["question"]["status"] == "active"


async def test_subjective_rubric_is_stored(client, who):
    who.author()
    question = (await client.post("/api/v1/questions", json=subjective())).json()["question"]
    assert [c["id"] for c in question["working"]["body"]["rubric"]] == ["clarity", "depth"]


async def test_assessment_work_follows_the_persons_permissions(client, act_as):
    """A super admin can stop one recruiter writing questions, or one staff member grading."""
    act_as(RECRUITER, role="recruiter", organization_id=EMPLOYER, scopes=("assessments.manage",), defaults=False)
    assert (await client.post("/api/v1/questions", json=mcq())).status_code == 403
    act_as(STAFF_A, role="staff", organization_id=ORG_A, defaults=False)
    assert (await client.get("/api/v1/grading/queue")).status_code == 403
    act_as(STAFF_A, role="staff", organization_id=ORG_A)
    assert (await client.get("/api/v1/grading/queue")).status_code == 200
