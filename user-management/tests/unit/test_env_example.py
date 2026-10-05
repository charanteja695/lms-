"""Every setting must be configurable from the env file, and the example files must be up to date."""

import re
from pathlib import Path

from app.core.config import Settings
from scripts.generate_env_example import DOCKER_OVERRIDES, LOCAL_OVERRIDES, render

ROOT = Path(__file__).resolve().parents[2]


def _names(text: str) -> set[str]:
    return set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, re.M))


def test_every_setting_is_listed_in_env_examples() -> None:
    for file_name in (".env.example", ".env.docker.example"):
        listed = _names((ROOT / file_name).read_text(encoding="utf-8"))
        missing = sorted(set(Settings.model_fields) - listed)
        assert not missing, f"{file_name} is missing {missing}; run python scripts/generate_env_example.py"


def test_env_examples_are_regenerated() -> None:
    assert (ROOT / ".env.example").read_text(encoding="utf-8") == render(
        LOCAL_OVERRIDES, "user-management: local settings", ".env"
    )
    assert (ROOT / ".env.docker.example").read_text(encoding="utf-8") == render(
        DOCKER_OVERRIDES, "user-management: docker compose settings", ".env.docker"
    )
