"""Generate docs/openapi.json and the Postman collection from the running code.

    python scripts/generate_api_artifacts.py

Run after any API change so the collection never drifts from the service. Every request in the
collection uses the examples defined in app/api/examples.py; login stores tokens automatically.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LOG_LEVEL", "ERROR")

from app.core.ids import EXAMPLE_ORGANIZATION_ID, EXAMPLE_SESSION_ID, EXAMPLE_USER_ID  # noqa: E402
from app.main import create_app  # noqa: E402

DOCS = ROOT / "docs"
COLLECTION_NAME = "LMS User Management API"

PATH_VARIABLES = {
    "user_id": "{{user_id}}",
    "organization_id": "{{organization_id}}",
    "session_id": "{{session_id}}",
    "job_id": "{{job_id}}",
}

LOGIN_TEST_SCRIPT = [
    "const body = pm.response.json();",
    "if (body.status === 'success' && body.token) {",
    "  pm.collectionVariables.set('access_token', body.token.access_token);",
    "  pm.collectionVariables.set('refresh_token', body.token.refresh_token);",
    "  pm.collectionVariables.set('my_user_id', body.user.user_id);",
    "}",
]
CAPTURE_IDS_SCRIPT = [
    "const body = pm.response.json();",
    "if (body.status !== 'success') { return; }",
    "const record = body.user || body.admin || body.institution;",
    "if (record && record.user_id) { pm.collectionVariables.set('user_id', record.user_id); }",
    "if (record && record.organization_id) { pm.collectionVariables.set('organization_id', record.organization_id); }",
]
COMMON_TEST_SCRIPT = [
    "pm.test('response uses the standard envelope', function () {",
    "  const type = pm.response.headers.get('Content-Type') || '';",
    "  if (!type.includes('application/json')) { return; }",
    "  const body = pm.response.json();",
    "  pm.expect(body).to.have.property('status');",
    "  pm.expect(body).to.have.property('code');",
    "  pm.expect(body).to.have.property('message');",
    "});",
]


def _query_params(operation: dict[str, Any]) -> list[dict[str, Any]]:
    params = []
    for parameter in operation.get("parameters", []):
        if parameter.get("in") != "query":
            continue
        schema = parameter.get("schema", {})
        example = schema.get("default")
        if example is None and "examples" in schema:
            example = schema["examples"][0]
        params.append(
            {
                "key": parameter["name"],
                "value": "" if example is None else str(example),
                "description": parameter.get("description") or schema.get("description", ""),
                "disabled": True,  # enable the filters you need
            }
        )
    return params


def _body(operation: dict[str, Any]) -> tuple[str | None, list[tuple[str, Any]]]:
    content = operation.get("requestBody", {}).get("content", {}).get("application/json")
    if not content:
        return None, []
    named = [(v.get("summary", k), v["value"]) for k, v in content.get("examples", {}).items()]
    if named:
        return json.dumps(named[0][1], indent=2, ensure_ascii=False), named
    return "{}", []


def _item(
    path: str, method: str, operation: dict[str, Any], body: str | None, name: str | None = None
) -> dict[str, Any]:
    url_path = path
    for key, variable in PATH_VARIABLES.items():
        url_path = url_path.replace("{" + key + "}", variable)
    segments = [segment for segment in url_path.split("/") if segment]
    request: dict[str, Any] = {
        "method": method.upper(),
        "header": [{"key": "Accept", "value": "application/json"}],
        "url": {
            "raw": "{{base_url}}" + url_path,
            "host": ["{{base_url}}"],
            "path": segments,
            "query": _query_params(operation),
        },
        "description": operation.get("description", ""),
    }
    if path.startswith("/api/v1/auth/") and path.rsplit("/", 1)[-1] in {
        "login", "refresh-token", "forgot-password", "verify-otp", "reset-password", "verify",
    }:  # fmt: skip
        request["auth"] = {"type": "noauth"}
    if "multipart/form-data" in operation.get("requestBody", {}).get("content", {}):
        request["body"] = {
            "mode": "formdata",
            "formdata": [
                {"key": "file", "type": "file", "src": [], "description": "CSV from /users/import/template"},
                {"key": "dry_run", "value": "true", "type": "text"},
                {"key": "mode", "value": "all_or_nothing", "type": "text", "description": "or skip_invalid"},
            ],
        }
    elif body is not None:
        request["header"].append({"key": "Content-Type", "value": "application/json"})
        request["body"] = {"mode": "raw", "raw": body, "options": {"raw": {"language": "json"}}}

    tests = list(COMMON_TEST_SCRIPT)
    if path.endswith(("/auth/login", "/auth/refresh-token")):
        tests += LOGIN_TEST_SCRIPT
    if method == "post" and path in {"/api/v1/users", "/api/v1/admins", "/api/v1/institutions"}:
        tests += CAPTURE_IDS_SCRIPT
    if path.endswith("/export-jobs"):
        tests += [
            "const body = pm.response.json();",
            "if (body.job) { pm.collectionVariables.set('job_id', body.job.job_id); }",
        ]
    if path.endswith("/auth/login"):
        tests += [
            "if (body.mfa_challenge) { pm.collectionVariables.set('mfa_token', body.mfa_challenge.mfa_token); }",
        ]
    return {
        "name": name or operation.get("summary", f"{method.upper()} {path}"),
        "request": request,
        "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": tests}}],
    }


def build_collection(spec: dict[str, Any]) -> dict[str, Any]:
    folders: dict[str, list[dict[str, Any]]] = {}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            tag = (operation.get("tags") or ["Other"])[0]
            body, named_examples = _body(operation)
            if len(named_examples) > 1:
                for summary, value in named_examples:
                    folders.setdefault(tag, []).append(
                        _item(path, method, operation, json.dumps(value, indent=2, ensure_ascii=False), summary)
                    )
            else:
                folders.setdefault(tag, []).append(_item(path, method, operation, body))

    return {
        "info": {
            "name": COLLECTION_NAME,
            "description": "Generated from the service's OpenAPI schema by scripts/generate_api_artifacts.py. "
            "Run 'Log in' first: tokens are stored automatically. Creating a user, admin or institution "
            "stores its user_id / organization_id for the following requests.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{access_token}}", "type": "string"}]},
        "variable": [
            {"key": "base_url", "value": "http://localhost:8001"},
            {"key": "access_token", "value": ""},
            {"key": "refresh_token", "value": ""},
            {"key": "my_user_id", "value": ""},
            {"key": "user_id", "value": EXAMPLE_USER_ID},
            {"key": "organization_id", "value": EXAMPLE_ORGANIZATION_ID},
            {"key": "session_id", "value": EXAMPLE_SESSION_ID},
            {"key": "job_id", "value": ""},
            {"key": "mfa_token", "value": ""},
        ],
        "item": [{"name": tag, "item": items} for tag, items in folders.items()],
    }


def main() -> None:
    spec = create_app().openapi()
    DOCS.mkdir(exist_ok=True)
    (DOCS / "postman").mkdir(exist_ok=True)
    (DOCS / "openapi.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    collection = build_collection(spec)
    target = DOCS / "postman" / "lms-user-management.postman_collection.json"
    target.write_text(json.dumps(collection, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    requests = sum(len(folder["item"]) for folder in collection["item"])
    print(f"Wrote docs/openapi.json ({len(spec['paths'])} paths) and {target.relative_to(ROOT)} ({requests} requests)")


if __name__ == "__main__":
    main()
