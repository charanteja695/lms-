"""An institution's academic structure: the head keeps departments -> programs -> sections and places students."""

from httpx import AsyncClient

from tests.conftest import API, Hierarchy, institution_payload


def _ids(structure: dict) -> tuple[str, str, str]:
    department = structure["departments"][0]
    program = department["programs"][0]
    return department["department_id"], program["program_id"], program["sections"][0]["section_id"]


async def test_the_head_builds_the_structure_and_places_students(client: AsyncClient, hierarchy: Hierarchy) -> None:
    base = f"{API}/institutions/{hierarchy.organization_id}"

    empty = (await client.get(f"{base}/academics", headers=hierarchy.head)).json()["academics"]
    assert empty["can_manage"] is True and empty["departments"] == []

    dept = await client.post(
        f"{base}/departments", json={"name": "Computer Science and Engineering", "code": "cse", "head_user_id": hierarchy.staff_id}, headers=hierarchy.head
    )
    assert dept.status_code == 201, dept.text
    department = dept.json()["academics"]["departments"][0]
    assert department["code"] == "CSE" and department["head"]["user_id"] == hierarchy.staff_id
    assert (await client.post(f"{base}/departments", json={"name": "Duplicate", "code": "CSE"}, headers=hierarchy.head)).status_code == 409
    # a head of department must be staff of this institution, not a student
    bad_head = await client.post(f"{base}/departments", json={"name": "Mechanical", "code": "ME", "head_user_id": hierarchy.student_id}, headers=hierarchy.head)
    assert bad_head.status_code == 422 and bad_head.json()["details"][0]["code"] == "NOT_STAFF_HERE"

    program = await client.post(
        f"{base}/programs", json={"department_id": department["department_id"], "name": "B.Tech Computer Science", "code": "BTCS", "duration_years": 4}, headers=hierarchy.head
    )
    assert program.status_code == 201, program.text
    program_id = program.json()["academics"]["departments"][0]["programs"][0]["program_id"]
    beyond = await client.post(f"{base}/sections", json={"program_id": program_id, "year_of_study": 5, "name": "A"}, headers=hierarchy.head)
    assert beyond.status_code == 422 and beyond.json()["details"][0]["code"] == "BEYOND_DURATION"
    section = await client.post(f"{base}/sections", json={"program_id": program_id, "year_of_study": 2, "name": "a"}, headers=hierarchy.head)
    assert section.status_code == 201, section.text
    _, _, section_id = _ids(section.json()["academics"])

    placed = await client.put(f"{base}/sections/{section_id}/students", json={"add": [hierarchy.student_id]}, headers=hierarchy.head)
    assert placed.status_code == 200 and placed.json()["changed"] == 1
    not_student = await client.put(f"{base}/sections/{section_id}/students", json={"add": [hierarchy.staff_id]}, headers=hierarchy.head)
    assert not_student.status_code == 422

    roster = (await client.get(f"{base}/sections/{section_id}/students", headers=hierarchy.staff)).json()
    assert roster["section"]["label"] == "BTCS · Year 2 · A" and roster["section"]["student_count"] == 1
    assert [s["user_id"] for s in roster["students"]] == [hierarchy.student_id]

    # placing fills the student's program / branch / year / section, which batches, reports and job eligibility read
    student = (await client.get(f"{API}/users/{hierarchy.student_id}", headers=hierarchy.head)).json()["user"]["student"]
    assert (student["program"], student["branch"], student["year_of_study"], student["section"]) == ("B.Tech Computer Science", "Computer Science and Engineering", 2, "A")

    # a renamed program rewrites its students' text fields
    await client.patch(f"{base}/programs/{program_id}", json={"name": "B.Tech CSE"}, headers=hierarchy.head)
    student = (await client.get(f"{API}/users/{hierarchy.student_id}", headers=hierarchy.head)).json()["user"]["student"]
    assert student["program"] == "B.Tech CSE"

    # nothing is removed out from under its students
    assert (await client.delete(f"{base}/sections/{section_id}", headers=hierarchy.head)).json()["code"] == "SECTION_HAS_STUDENTS"
    assert (await client.delete(f"{base}/programs/{program_id}", headers=hierarchy.head)).json()["code"] == "PROGRAM_HAS_SECTIONS"
    assert (await client.delete(f"{base}/departments/{department['department_id']}", headers=hierarchy.head)).json()["code"] == "DEPARTMENT_HAS_PROGRAMS"
    await client.put(f"{base}/sections/{section_id}/students", json={"remove": [hierarchy.student_id]}, headers=hierarchy.head)
    gone = await client.delete(f"{base}/sections/{section_id}", headers=hierarchy.head)
    assert gone.status_code == 200 and gone.json()["academics"]["totals"]["sections"] == 0


async def test_staff_read_it_students_and_other_institutions_cannot(client: AsyncClient, hierarchy: Hierarchy) -> None:
    base = f"{API}/institutions/{hierarchy.organization_id}"
    await client.post(f"{base}/departments", json={"name": "Physics", "code": "PHY"}, headers=hierarchy.head)

    staff_view = (await client.get(f"{base}/academics", headers=hierarchy.staff)).json()["academics"]
    assert staff_view["can_manage"] is False and staff_view["departments"][0]["code"] == "PHY"
    assert (await client.post(f"{base}/departments", json={"name": "Chemistry", "code": "CHE"}, headers=hierarchy.staff)).status_code == 403
    assert (await client.get(f"{base}/academics", headers=hierarchy.student)).status_code == 403

    # the owning admin and the super admin keep it too
    assert (await client.post(f"{base}/departments", json={"name": "Chemistry", "code": "CHE"}, headers=hierarchy.admin)).status_code == 201
    assert (await client.post(f"{base}/departments", json={"name": "Maths", "code": "MAT"}, headers=hierarchy.root)).status_code == 201

    # another institution's people never see it
    other = await client.post(f"{API}/institutions", json={**institution_payload("OTHER-01"), "admin_user_id": hierarchy.admin_id}, headers=hierarchy.root)
    assert other.status_code == 201, other.text
    other_base = f"{API}/institutions/{other.json()['institution']['organization_id']}"
    assert (await client.get(f"{other_base}/academics", headers=hierarchy.head)).status_code == 404

    menu = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.head)).json()["permissions"]
    assert "academics" in menu["sections"] and menu["academics"] == {"view": True, "manage": True}
    staff_menu = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.staff)).json()["permissions"]
    assert staff_menu["academics"] == {"view": True, "manage": False}
    student_menu = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.student)).json()["permissions"]
    assert "academics" not in student_menu["sections"]


async def test_the_organisation_tree_shows_each_person_their_part(client: AsyncClient, hierarchy: Hierarchy) -> None:
    root = (await client.get(f"{API}/hierarchy", headers=hierarchy.root)).json()["hierarchy"]
    assert root["super_admins"] and root["totals"]["institutions"] == 1 and root["totals"]["students"] == 1
    branch = next(a for a in root["admins"] if a["admin"] and a["admin"]["user_id"] == hierarchy.admin_id)
    institution = branch["institutions"][0]
    assert institution["organization_id"] == hierarchy.organization_id
    assert [h["user_id"] for h in institution["heads"]] == [hierarchy.head_id] and (institution["staff"], institution["students"]) == (1, 1)

    mine = (await client.get(f"{API}/hierarchy", headers=hierarchy.admin)).json()["hierarchy"]
    assert mine["super_admins"] == [] and [a["admin"]["user_id"] for a in mine["admins"]] == [hierarchy.admin_id]
    head = (await client.get(f"{API}/hierarchy", headers=hierarchy.head)).json()["hierarchy"]
    assert head["totals"]["institutions"] == 1
    assert (await client.get(f"{API}/hierarchy", headers=hierarchy.student)).status_code == 403
    sections = (await client.get(f"{API}/users/me/permissions", headers=hierarchy.head)).json()["permissions"]["sections"]
    assert "hierarchy" in sections


async def test_an_admins_token_names_the_institutions_they_look_after(client: AsyncClient, hierarchy: Hierarchy) -> None:
    """Other services limit accounts.manage to these for an admin (the super admin reaches every institution)."""
    import jwt

    from tests.conftest import NEW_PASSWORD, bearer, login

    fresh = bearer(await login(client, "admin1", NEW_PASSWORD))  # signed in after the institution was assigned
    claims = jwt.decode(fresh["Authorization"].removeprefix("Bearer "), options={"verify_signature": False})
    assert claims["admin_orgs"] == [hierarchy.organization_id]
    head = jwt.decode(hierarchy.head["Authorization"].removeprefix("Bearer "), options={"verify_signature": False})
    assert "admin_orgs" not in head
