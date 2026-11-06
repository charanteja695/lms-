"""Properties of the whole API surface that no single endpoint test would notice."""

from app.main import app


def test_every_success_envelope_keeps_its_success_code() -> None:
    """A resource field named `code` would silently replace the envelope's `code: SUCCESS` (it once did)."""
    schemas = app.openapi()["components"]["schemas"]
    responses = {
        name: schema
        for name, schema in schemas.items()
        if name.endswith("Response") and schema.get("properties", {}).get("status", {}).get("const") == "success"
    }
    assert len(responses) >= 15  # (guards this test against silently checking nothing)
    for name, schema in responses.items():
        code = schema["properties"].get("code", {})
        assert code.get("const") == "SUCCESS" or code.get("enum") == ["SUCCESS"], f"{name}.code is {code}"


def test_every_operation_documents_its_authentication_failure() -> None:
    """Except the health probes, every route sits behind a token, so a 401 must be in its documented responses."""
    open_paths = {"/health/live", "/health/ready"}
    for path, operations in app.openapi()["paths"].items():
        if path in open_paths or path.startswith("/api/v1/internal"):
            continue
        for method, operation in operations.items():
            assert "401" in operation["responses"], f"{method.upper()} {path} does not document 401"


def test_no_route_exposes_test_case_data_to_students_by_type() -> None:
    """The only response schemas that can carry hidden test data are the author/review ones."""
    schemas = app.openapi()["components"]["schemas"]
    carriers = {
        name
        for name, schema in schemas.items()
        if {"input", "expected"} <= set(schema.get("properties", {})) and not name.endswith(("Create", "Update"))  # request bodies
    }
    assert carriers == {"TestCaseOut", "SampleCaseOut", "CaseResultOut"}  # decrypted, sample-only, and sample-only-in-a-result
