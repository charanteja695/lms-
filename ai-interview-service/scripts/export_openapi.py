"""Write docs/openapi.json from the running app's schema. Import it into Postman (Import -> the file) or any client
generator; regenerate after changing an endpoint.

    python scripts/export_openapi.py
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "insecure-dev-internal-service-token-change-me-0")

from app.main import app  # noqa: E402

target = ROOT / "docs" / "openapi.json"
target.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {target.relative_to(ROOT)} ({sum(len(operations) for operations in app.openapi()['paths'].values())} operations)")
