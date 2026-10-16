"""The names-only organisation directory: platform staff can find any organisation; members cannot."""

from httpx import AsyncClient

from tests.conftest import API, Hierarchy, activate_account, admin_payload


async def test_a_scoped_admin_finds_organisations_they_do_not_own(client: AsyncClient, hierarchy: Hierarchy) -> None:
    created = await client.post(f"{API}/admins", json={**admin_payload("analyst1"), "scopes": ["analytics.view"]}, headers=hierarchy.root)
    assert created.status_code == 201, created.text
    analyst = await activate_account(client, "analyst1")

    # Their own institutions list is empty (they own none) ...
    assert (await client.get(f"{API}/institutions", headers=analyst)).json()["institutions"] == []
    # ... but the directory finds hierarchy.admin's institution, by name or code, with names only.
    response = await client.get(f"{API}/directory/organizations", params={"type": "institution", "search_text": "sph"}, headers=analyst)
    assert response.status_code == 200, response.text
    [entry] = response.json()["organizations"]
    assert entry["organization_id"] == hierarchy.organization_id and entry["organization_type"] == "institution"
    assert set(entry) == {"organization_id", "organization_type", "name", "code", "city", "status"}
    assert response.json()["page_context"]["total_records"] == 1

    one = await client.get(f"{API}/directory/organizations/{hierarchy.organization_id}", headers=analyst)
    assert one.status_code == 200 and one.json()["organization"]["code"] == entry["code"]
    # institutions and employers never mix
    assert (await client.get(f"{API}/directory/organizations", params={"type": "employer"}, headers=analyst)).json()["organizations"] == []


async def test_members_cannot_use_the_directory(client: AsyncClient, hierarchy: Hierarchy) -> None:
    for headers in (hierarchy.head, hierarchy.staff, hierarchy.student):
        assert (await client.get(f"{API}/directory/organizations", params={"type": "institution"}, headers=headers)).status_code == 403
        assert (await client.get(f"{API}/directory/organizations/{hierarchy.organization_id}", headers=headers)).status_code == 403
    assert (await client.get(f"{API}/directory/organizations", params={"type": "institution"}, headers=hierarchy.root)).status_code == 200
