"""Offline Alembic validation — no Postgres required.

Verifies revision chain integrity and that migration files are loadable.
Run: python scripts/validate_alembic.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        print(f"FAIL: expected 1 head, got {heads}")
        return 1
    rev = heads[0]
    print(f"OK: single head revision {rev}")
    for rev_obj in script.walk_revisions():
        print(f"  - {rev_obj.revision}: {rev_obj.doc}")
    versions = list(ROOT.glob("alembic/versions/*.py"))
    if not versions:
        print("FAIL: no migration files in alembic/versions/")
        return 1
    print(f"OK: {len(versions)} migration file(s)")
    print("Alembic history is clean (offline check). Run `alembic upgrade head` when Postgres is up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
