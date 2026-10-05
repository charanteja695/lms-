"""python -m app.cli register-prompts --gateway-url http://localhost:8010 --token <an AI manager's access token>

Registers this service's prompts in ai-gateway's prompt registry as *draft* versions. A second AI manager must then
activate each one (the gateway refuses to let an author activate their own version), so nothing goes live unreviewed.
Safe to re-run: an existing prompt key is kept and a new draft version is added.
"""

import argparse
import sys

import httpx

from app.ai.prompts import ALL


def register(gateway_url: str, token: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    failures = 0
    with httpx.Client(base_url=gateway_url.rstrip("/") + "/api/v1", headers=headers, timeout=15) as client:
        for definition in ALL:
            created = client.post(
                "/prompts", json={"key": definition.key, "capability": "chat", "owner_service": "ai-interview-service", "description": definition.description}
            )
            if created.status_code not in (201, 409):
                print(f"{definition.key}: could not create prompt ({created.status_code} {created.text[:200]})")
                failures += 1
                continue
            version = client.post(
                f"/prompts/{definition.key}/versions",
                json={"template": definition.template, "variables": list(definition.variables), "allowed_tools": [], "model_params": definition.model_params},
            )
            if version.status_code != 201:
                print(f"{definition.key}: could not create a version ({version.status_code} {version.text[:200]})")
                failures += 1
                continue
            number = version.json()["version"]["version"]
            print(f"{definition.key}: draft version {number} created — a different AI manager must activate it")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register-prompts", help="register this service's prompts in ai-gateway as drafts")
    reg.add_argument("--gateway-url", required=True)
    reg.add_argument("--token", required=True)
    args = parser.parse_args()
    return 1 if register(args.gateway_url, args.token) else 0


if __name__ == "__main__":
    sys.exit(main())
