"""Pickers: a head finds a verified company for a drive; a recruiter finds an institution to restrict a job to."""

from tests.conftest import API, EMP_A, ORG_B, seed_world, verify_employer


async def test_only_verified_companies_are_listed_and_names_filter(client, who, send_event):
    await seed_world(send_event)
    who.head()
    assert (await client.get(f"{API}/directory/companies")).json()["organizations"] == []  # nobody verified yet
    await verify_employer(client, who)
    who.head()
    listed = (await client.get(f"{API}/directory/companies")).json()["organizations"]
    assert [(o["organization_id"], o["name"]) for o in listed] == [(str(EMP_A), "Acme Labs")]
    assert (await client.get(f"{API}/directory/companies", params={"q": "beta"})).json()["organizations"] == []


async def test_institutions_are_for_a_companys_team_and_careers_managers(client, who, send_event):
    await seed_world(send_event)
    who.recruiter()
    names = [o["name"] for o in (await client.get(f"{API}/directory/institutions")).json()["organizations"]]
    assert names == ["Anna University", "Bharat College"]
    only = (await client.get(f"{API}/directory/institutions", params={"q": "bharat"})).json()["organizations"]
    assert [o["organization_id"] for o in only] == [str(ORG_B)]
    who.manager()
    assert len((await client.get(f"{API}/directory/institutions")).json()["organizations"]) == 2
    for act in (who.student, who.head):
        act()
        assert (await client.get(f"{API}/directory/institutions")).status_code == 403
