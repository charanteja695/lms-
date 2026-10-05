"""Write config/routes.json (the route table) and config/route_inventory.json (every path of every service it was built from).

    python scripts/generate_routes.py            # rewrite both files from the services' running apps
    python scripts/generate_routes.py --check    # exit 1 if the committed files are out of date (for CI)

Each service's paths are read by importing its app with its own virtualenv (``<service>/.venv``) and asking FastAPI for its OpenAPI schema: nothing is
guessed from documentation, and a new endpoint or service shows up as a diff the next time this runs. It fails if two services claim the same path.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT.parent
sys.path.insert(0, str(ROOT))

from app.proxy.routes import compile_rules, to_json  # noqa: E402

DUMP = (
    "import json, os;"
    "os.environ.setdefault('ANTHROPIC_API_KEY','x'); os.environ.setdefault('VOYAGE_API_KEY','x');"
    "from app.main import create_app;"
    "print('PATHS=' + json.dumps(sorted(create_app().openapi()['paths'])))"
)


def python_of(service: Path) -> Path | None:
    for candidate in (service / ".venv" / "Scripts" / "python.exe", service / ".venv" / "bin" / "python"):
        if candidate.exists():
            return candidate
    return None


def services() -> list[Path]:
    return sorted(d for d in BACKEND.iterdir() if d.is_dir() and (d / "app" / "main.py").exists() and d.name != "api-gateway")


def read_paths(service: Path) -> list[str]:
    python = python_of(service)
    if python is None:
        raise SystemExit(f"{service.name}: no virtualenv at {service / '.venv'} — create it (pip install -r requirements-dev.txt) so its routes can be read")
    result = subprocess.run(  # noqa: S603
        [str(python), "-c", DUMP], cwd=service, env={**os.environ, "ENVIRONMENT": "test", "LOG_JSON": "false"}, capture_output=True, text=True, check=False, timeout=180
    )
    line = next((ln for ln in result.stdout.splitlines() if ln.startswith("PATHS=")), None)
    if result.returncode != 0 or line is None:
        raise SystemExit(f"{service.name}: could not read its routes:\n{result.stderr[-800:]}")
    return list(json.loads(line[len("PATHS="):]))


def build() -> tuple[dict[str, list[dict[str, str]]], dict[str, dict[str, list[str]]]]:
    inventory: dict[str, list[str]] = {service.name: read_paths(service) for service in services()}
    pairs = [(path, name) for name, paths in inventory.items() for path in paths]
    rules = to_json(compile_rules(pairs))
    return {"rules": rules}, {"services": inventory}


def main() -> int:
    routes, inventory = build()
    files = {ROOT / "config" / "routes.json": routes, ROOT / "config" / "route_inventory.json": inventory}
    rendered = {path: json.dumps(data, indent=2) + "\n" for path, data in files.items()}
    if "--check" in sys.argv:
        stale = [p.name for p, text in rendered.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            print(f"out of date: {', '.join(stale)} — run scripts/generate_routes.py")
            return 1
        print("route table is up to date")
        return 0
    for path, text in rendered.items():
        path.write_text(text, encoding="utf-8")
    rules = routes["rules"]
    services = inventory["services"]
    print(f"wrote config/routes.json ({len(rules)} rules) and config/route_inventory.json ({sum(len(v) for v in services.values())} paths, {len(services)} services)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
