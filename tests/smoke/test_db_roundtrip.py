"""
Offline round-trip test for the consolidated DB scripts (scripts/db/).

Exports the live local SQLite to JSON, re-imports into a throwaway DB, and
asserts the row counts survive the round trip. Read-only against the real DB
(export reads it; import writes only to a temp file). Skipped if the local DB
is absent.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DB_DIR = ROOT / "scripts" / "db"
LIVE_DB = Path.home() / ".claude" / "data" / "ig-control-tower.db"
TABLES = ("generic_opportunities", "company_analyses", "company_profiles")


def _counts(db: Path) -> dict:
    con = sqlite3.connect(str(db))
    try:
        return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    finally:
        con.close()


@pytest.mark.skipif(not LIVE_DB.exists(), reason="local SQLite DB not present")
def test_export_import_round_trip(tmp_path):
    export_dir = tmp_path / "db_export"
    fresh_db = tmp_path / "fresh.db"

    src = _counts(LIVE_DB)
    assert src["generic_opportunities"] >= 1791

    export = subprocess.run(
        [sys.executable, str(DB_DIR / "export_db.py"), str(export_dir), str(LIVE_DB)],
        capture_output=True, text=True,
    )
    assert export.returncode == 0, export.stderr
    assert (export_dir / "generic_opportunities.json").exists()

    env = dict(os.environ, IG_CONTROL_TOWER_DB_PATH=str(fresh_db))
    imp = subprocess.run(
        [sys.executable, str(DB_DIR / "import_db.py"), str(export_dir), str(fresh_db)],
        capture_output=True, text=True, env=env,
    )
    assert imp.returncode == 0, imp.stderr

    assert _counts(fresh_db) == src
