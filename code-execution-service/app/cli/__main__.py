"""python -m app.cli <command>

  sync-languages     upsert runtimes/languages.json into the database (run on every deploy)
  verify-languages   check each enabled language's engine id against the running Judge0 (exit 1 on a bad id)
  rotate-keys        re-encrypt every stored test case under the newest TEST_CASE_ENCRYPTION_KEYS key
"""

import argparse
import asyncio
import sys

from app.cli import commands
from app.core.config import get_settings
from app.db.session import build_engine, build_sessionmaker
from app.engines.base import EngineError


async def _run(command: str) -> int:
    settings = get_settings()
    engine = build_engine(settings)
    sessionmaker = build_sessionmaker(engine)
    try:
        if command == "sync-languages":
            created, updated = await commands.sync_languages(sessionmaker, settings)
            print(f"languages: {created} created, {updated} updated")
        elif command == "verify-languages":
            try:
                checks = await commands.verify_languages(sessionmaker, settings)
            except EngineError as exc:
                print(f"cannot reach Judge0 at {settings.JUDGE0_URL}: {exc}")
                return 2
            for check in checks:
                status = "ok     " if check.ok else "MISSING"
                print(f"{status} {check.code:<12} id={check.configured_id!s:<5} engine says: {check.engine_name or '-'}")
            bad = [check for check in checks if not check.ok]
            print(f"{len(checks) - len(bad)} of {len(checks)} ids exist on the engine; compare the names above with your intent")
            return 1 if bad else 0
        elif command == "rotate-keys":
            print(f"re-encrypted {await commands.rotate_keys(sessionmaker, settings)} values")
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["sync-languages", "verify-languages", "rotate-keys"])
    return asyncio.run(_run(parser.parse_args().command))


if __name__ == "__main__":
    sys.exit(main())
