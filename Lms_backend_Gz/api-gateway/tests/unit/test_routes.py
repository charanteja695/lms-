"""The route table: longest-prefix matching, what is never routed, and that the committed table is exactly what the committed inventory compiles to."""

import json
from pathlib import Path

import pytest

from app.proxy.routes import RouteConflictError, RouteTable, compile_rules, normalise, to_json

CONFIG = Path(__file__).resolve().parents[2] / "config"


def table(inventory: list[tuple[str, str]]) -> RouteTable:
    return RouteTable({pattern: service for pattern, service in compile_rules(inventory)})


def test_a_shared_first_segment_is_split_by_the_next_one():
    routes = table([("/api/v1/employer/jobs", "jobs"), ("/api/v1/employer/plans", "billing"), ("/api/v1/employer/interviews/{id}", "interviews")])
    assert routes.resolve("/api/v1/employer/jobs") == "jobs"
    assert routes.resolve("/api/v1/employer/jobs/123/applications") == "jobs"
    assert routes.resolve("/api/v1/employer/plans/growth/purchase") == "billing"
    assert routes.resolve("/api/v1/employer/interviews/9") == "interviews"
    assert routes.resolve("/api/v1/employer/unknown") is None


def test_a_prefix_owned_by_one_service_stays_one_short_rule():
    rules = dict(compile_rules([("/api/v1/tickets", "support"), ("/api/v1/tickets/{id}", "support"), ("/api/v1/tickets/{id}/messages", "support")]))
    assert rules == {("api", "v1", "tickets"): "support"}


def test_a_parameter_matches_any_one_segment_and_a_literal_beats_it():
    routes = table([("/api/v1/tests/{test_id}/attempts", "assessment"), ("/api/v1/tests/mine", "mine"), ("/api/v1/tests", "assessment")])
    assert routes.resolve("/api/v1/tests/abc/attempts") == "assessment"
    assert routes.resolve("/api/v1/tests/mine") == "mine"


def test_two_services_claiming_one_path_is_a_conflict():
    with pytest.raises(RouteConflictError, match="both"):
        compile_rules([("/api/v1/templates", "a"), ("/api/v1/templates", "b")])


@pytest.mark.parametrize(
    "path",
    ["/api/v1/internal/runs", "/api/v1/tickets/internal/x", "/health/live", "/health/ready", "/docs", "/openapi.json", "/redoc", "/", "/api/v1/internal"],
)
def test_internal_health_and_docs_paths_are_never_routed(path):
    routes = table([("/api/v1/tickets", "support"), ("/api/v1/internal/runs", "exec"), ("/health/live", "support"), ("/docs", "support")])
    assert routes.resolve(path) is None


def test_the_committed_route_table_is_what_the_committed_inventory_compiles_to():
    inventory = json.loads((CONFIG / "route_inventory.json").read_text(encoding="utf-8"))["services"]
    pairs = [(path, service) for service, paths in inventory.items() for path in paths]
    committed = json.loads((CONFIG / "routes.json").read_text(encoding="utf-8"))["rules"]
    assert committed == to_json(compile_rules(pairs)), "config/routes.json is stale: run scripts/generate_routes.py"


def test_every_path_of_every_service_reaches_that_service_and_no_internal_path_is_reachable():
    inventory = json.loads((CONFIG / "route_inventory.json").read_text(encoding="utf-8"))["services"]
    routes = RouteTable.from_json(json.loads((CONFIG / "routes.json").read_text(encoding="utf-8"))["rules"])
    checked = internal = 0
    for service, paths in inventory.items():
        for template in paths:
            concrete = "/" + "/".join("probe0" if part.startswith("{") else part for part in template.split("/") if part)
            if "internal" in template.split("/") or template.startswith(("/health", "/docs", "/redoc", "/openapi")):
                assert routes.resolve(concrete) is None, template
                internal += 1
            else:
                assert routes.resolve(concrete) == service, template
                checked += 1
    assert checked > 300 and internal >= 10


def test_normalise_turns_parameters_into_wildcards():
    assert normalise("/api/v1/tests/{test_id}/attempts") == ("api", "v1", "tests", "*", "attempts")
