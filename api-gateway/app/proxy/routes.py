"""The route table: which service a request path belongs to.

The services' paths do not share one prefix per service — ``/api/v1/employer`` alone is served by three of them, ``/api/v1/admin`` by three, ``jobs``
by two, and so on — so a route is a path *prefix of any depth*, matched longest-first, where ``*`` stands for one path parameter (``/api/v1/tests/*/attempts``).
``compile_rules`` turns the full inventory of every service's paths (read from the running apps by ``scripts/generate_routes.py``) into the smallest set of
prefixes that still sends every one of those paths to its own service, and refuses to compile if two services claim the same path.

Never routed, however a path is spelled: anything with an ``internal`` segment (service-to-service calls authenticated by the shared internal token, never
for a browser), each service's own ``/health`` and API docs.
"""

from collections import defaultdict
from dataclasses import dataclass, field

WILDCARD = "*"
BLOCKED_SEGMENTS = frozenset({"internal"})
BLOCKED_ROOTS = frozenset({"health", "docs", "redoc", "openapi.json"})
PROBE = "probe0"


def segments(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def normalise(template: str) -> tuple[str, ...]:
    """``/api/v1/tests/{test_id}/attempts`` -> ``("api", "v1", "tests", "*", "attempts")``."""
    return tuple(WILDCARD if part.startswith("{") and part.endswith("}") else part for part in segments(template))


def is_public_candidate(template: str) -> bool:
    parts = segments(template)
    return bool(parts) and parts[0] not in BLOCKED_ROOTS and not BLOCKED_SEGMENTS.intersection(parts)


class RouteConflictError(ValueError):
    pass


def compile_rules(inventory: list[tuple[str, str]]) -> list[tuple[tuple[str, ...], str]]:
    """``inventory``: ``(path template, service)`` pairs. Returns ``(pattern, service)`` rules, then verifies every inventory path resolves to its service."""
    entries: dict[tuple[str, ...], str] = {}
    for template, service in inventory:
        if not is_public_candidate(template):
            continue
        pattern = normalise(template)
        if entries.setdefault(pattern, service) != service:
            raise RouteConflictError(f"{template} is served by both {entries[pattern]} and {service}")

    rules: dict[tuple[str, ...], str] = {}

    def build(group: list[tuple[str, ...]], depth: int) -> None:
        by_prefix: dict[tuple[str, ...], list[tuple[str, ...]]] = defaultdict(list)
        for pattern in group:
            by_prefix[pattern[:depth]].append(pattern)
        for prefix, members in by_prefix.items():
            services = {entries[m] for m in members}
            if len(services) == 1:
                rules[prefix] = services.pop()
                continue
            for member in members:
                if len(member) == depth:
                    rules[member] = entries[member]  # an exact path that shares its prefix with other services' deeper paths
            build([m for m in members if len(m) > depth], depth + 1)

    # Never a rule shorter than the resource itself (/api/v1/<resource>): an unknown /api/v1/whatever must not fall through to whichever service happens to be alone
    # under /api. Anything outside /api/v1 (the JWKS document) is routed by its exact path.
    api = [p for p in entries if p[:2] == ("api", "v1")]
    for pattern in entries:
        if pattern[:2] != ("api", "v1"):
            rules[pattern] = entries[pattern]
    build(api, min(3, max((len(p) for p in api), default=3)))
    table = RouteTable(rules)
    for pattern, service in entries.items():
        probe = "/" + "/".join(PROBE if part == WILDCARD else part for part in pattern)
        if table.resolve(probe) != service:
            raise RouteConflictError(f"{probe} would be sent to {table.resolve(probe)}, not {service}")
    return sorted(rules.items(), key=lambda item: (item[0], item[1]))


@dataclass(slots=True)
class _Node:
    children: dict[str, "_Node"] = field(default_factory=dict)
    service: str | None = None


class RouteTable:
    def __init__(self, rules: dict[tuple[str, ...], str]) -> None:
        self._root = _Node()
        self.rules = dict(rules)
        for pattern, service in rules.items():
            node = self._root
            for part in pattern:
                node = node.children.setdefault(part, _Node())
            node.service = service

    @classmethod
    def from_json(cls, rules: list[dict[str, str]]) -> "RouteTable":
        return cls({normalise(rule["path"]): rule["service"] for rule in rules})

    def resolve(self, path: str) -> str | None:
        """The service whose longest matching prefix covers ``path``; ``None`` if none does or the path is one that is never routed."""
        parts = segments(path)
        if not parts or parts[0] in BLOCKED_ROOTS or BLOCKED_SEGMENTS.intersection(parts):
            return None
        return self._walk(self._root, parts, 0)

    def _walk(self, node: _Node, parts: list[str], index: int) -> str | None:
        best = node.service if index > 0 else None
        if index == len(parts):
            return best
        for key in (parts[index], WILDCARD):
            child = node.children.get(key)
            if child is not None:
                found = self._walk(child, parts, index + 1)
                if found is not None:
                    return found  # a deeper match beats this node's own
            if key == WILDCARD:
                break
        return best


def to_json(rules: list[tuple[tuple[str, ...], str]]) -> list[dict[str, str]]:
    return [{"path": "/" + "/".join(pattern), "service": service} for pattern, service in rules]
