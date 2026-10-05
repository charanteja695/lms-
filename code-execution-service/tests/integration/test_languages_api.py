from httpx import AsyncClient

from tests.conftest import STUDENT

V1 = "/api/v1"


async def test_everything_needs_a_signed_in_user(client: AsyncClient) -> None:
    for method, path in (("GET", "/languages"), ("GET", "/languages/all"), ("POST", "/languages"), ("PATCH", "/languages/python3")):
        response = await client.request(method, f"{V1}{path}")
        assert response.status_code == 401, path
        assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_the_editor_gets_every_enabled_language_with_what_it_needs_to_switch(client: AsyncClient, as_student) -> None:
    as_student()
    languages = (await client.get(f"{V1}/languages")).json()["languages"]
    codes = [language["code"] for language in languages]

    # The blueprint's v1 list (docs/PRODUCT.md §5.2), each with its own file name and starter code.
    assert {"c", "cpp17", "cpp20", "java", "python3", "javascript", "typescript", "go", "rust", "csharp", "kotlin",
            "php", "ruby", "swift", "r", "bash", "sqlite"} <= set(codes)
    assert "postgresql" not in codes  # needs a sandbox cluster, so it ships disabled
    by_code = {language["code"]: language for language in languages}
    assert by_code["java"]["file_name"] == "Main.java" and "public class Main" in by_code["java"]["starter_template"]
    assert by_code["python3"]["editor_mode"] == "python" and by_code["python3"]["version"] == "3.12"
    assert by_code["sqlite"]["kind"] == "sql"
    assert all("engine_language_id" not in language for language in languages)  # engine internals stay internal
    assert codes[0] == "c" and codes[-1] == "sqlite"  # in the catalogue's sort order


async def test_only_a_super_admin_sees_engine_settings_and_disabled_languages(client: AsyncClient, as_student, as_author, as_super_admin) -> None:
    for sign_in in (as_student, as_author):
        sign_in()
        assert (await client.get(f"{V1}/languages/all")).status_code == 403

    as_super_admin()
    languages = (await client.get(f"{V1}/languages/all")).json()["languages"]
    by_code = {language["code"]: language for language in languages}
    assert by_code["postgresql"]["enabled"] is False
    assert by_code["cpp20"]["engine_language_id"] == 54 and by_code["cpp20"]["compiler_options"] == "-std=c++20 -O2"
    assert by_code["python3"]["time_multiplier"] == 3.0  # slower runtimes get more time


async def test_a_super_admin_can_add_and_change_languages(client: AsyncClient, as_super_admin, as_student) -> None:
    as_super_admin()
    body = {"code": "zig", "name": "Zig", "version": "0.13", "file_name": "main.zig", "editor_mode": "zig", "engine_language_id": 999}
    created = await client.post(f"{V1}/languages", json=body)
    assert created.status_code == 201 and created.json()["language"]["code"] == "zig"
    assert (await client.post(f"{V1}/languages", json=body)).json()["code"] == "LANGUAGE_EXISTS"

    patched = await client.patch(f"{V1}/languages/zig", json={"enabled": False, "time_multiplier": 1.5})
    assert patched.json()["language"]["enabled"] is False and patched.json()["language"]["time_multiplier"] == 1.5

    as_student()
    assert "zig" not in [language["code"] for language in (await client.get(f"{V1}/languages")).json()["languages"]]
    as_super_admin()
    await client.patch(f"{V1}/languages/postgresql", json={"enabled": True})
    as_student()
    assert "postgresql" in [language["code"] for language in (await client.get(f"{V1}/languages")).json()["languages"]]


async def test_language_changes_are_validated_and_restricted(client: AsyncClient, as_student, as_super_admin) -> None:
    as_student(STUDENT)
    assert (await client.post(f"{V1}/languages", json={"code": "x"})).status_code == 403
    assert (await client.patch(f"{V1}/languages/python3", json={"enabled": False})).status_code == 403

    as_super_admin()
    assert (await client.patch(f"{V1}/languages/nope", json={"enabled": False})).status_code == 404
    assert (await client.patch(f"{V1}/languages/python3", json={"time_multiplier": 500})).status_code == 422
    assert (await client.patch(f"{V1}/languages/python3", json={"kind": "cobol"})).status_code == 422
    assert (await client.patch(f"{V1}/languages/python3", json={"surprise": 1})).status_code == 422  # unknown fields are refused
