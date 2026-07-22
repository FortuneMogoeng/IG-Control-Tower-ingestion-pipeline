#!/usr/bin/env python3
"""Rebuild / refresh the local IG Control Tower SQLite database from the JSON export.

Idempotent: UPSERTs by natural key (opportunity_id / analysis_id / company_slug), so
re-running is safe and merging two teammates' exports then importing "just works".

Usage:
    python import_db.py [--if-missing] [export_dir] [db_path]

    --if-missing : do nothing if the DB already exists AND has rows (handy as a hook).
    export_dir   : default <plugin>/data/db_export
    db_path      : default $IG_CONTROL_TOWER_DB_PATH or ~/.claude/data/ig-control-tower.db
"""
import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Load a local .env (repo root / cwd / ~) so AZURE_STORAGE_* / IG_CONTROL_TOWER_* etc.
# are available without the caller having to export them. Real env vars take precedence.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from _envload import load_dotenv as _load_dotenv
    _load_dotenv()
except Exception:
    pass

# Standalone layout (this repo): scripts/db/import_db.py -> repo root is parents[2].
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORT = REPO_ROOT / "data" / "db_export"
INIT_DB = Path(__file__).resolve().parent / "init_db.py"
DEFAULT_DB = Path(os.environ.get("IG_CONTROL_TOWER_DB_PATH",
                                 Path.home() / ".claude" / "data" / "ig-control-tower.db"))
DEFAULT_METRICS = Path(os.environ.get("IG_CONTROL_TOWER_METRICS_PATH",
                                      Path.home() / ".claude" / "data" / "ig-control-tower-metrics.json"))


def table_columns(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def upsert(conn, table, key_col, records, transform=None):
    if not records:
        return 0
    cols = set(table_columns(conn, table))
    n = 0
    for rec in records:
        if transform:
            rec = transform(conn, dict(rec))
            if rec is None:
                continue
        rec = {k: v for k, v in rec.items() if k in cols}
        # serialise dict/list values to JSON text (the schema stores them as TEXT)
        for k, v in list(rec.items()):
            if isinstance(v, (dict, list)):
                rec[k] = json.dumps(v, ensure_ascii=False)
        if key_col not in rec or rec[key_col] in (None, ""):
            continue
        names = list(rec.keys())
        placeholders = ",".join("?" for _ in names)
        update_set = ",".join(f"{c}=excluded.{c}" for c in names if c != key_col)
        if "updated_at" in cols and "updated_at" not in names:
            update_set += ", updated_at=CURRENT_TIMESTAMP"
        sql = (f"INSERT INTO {table} ({','.join(names)}) VALUES ({placeholders}) "
               f"ON CONFLICT({key_col}) DO UPDATE SET {update_set}")
        conn.execute(sql, [rec[c] for c in names])
        n += 1
    return n


def resolve_fk(conn, rec):
    """company_analyses: turn generic_opportunity_opportunity_id (string) back into the rowid FK."""
    oppid = rec.pop("generic_opportunity_opportunity_id", None)
    if oppid:
        row = conn.execute("SELECT id FROM generic_opportunities WHERE opportunity_id = ?", (oppid,)).fetchone()
        rec["generic_opportunity_id"] = row[0] if row else None
    return rec


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if_missing = "--if-missing" in flags
    export_dir = Path(args[0]) if len(args) >= 1 else DEFAULT_EXPORT
    db_path = Path(args[1]) if len(args) >= 2 else DEFAULT_DB

    if not export_dir.exists():
        print(f"ERROR: export dir not found: {export_dir}")
        sys.exit(1)

    if if_missing and db_path.exists():
        try:
            c = sqlite3.connect(str(db_path))
            n = c.execute("SELECT count(*) FROM generic_opportunities").fetchone()[0]
            c.close()
            if n > 0:
                print(f"DB already present with {n} generic_opportunities at {db_path} — nothing to do (--if-missing).")
                return
        except sqlite3.Error:
            pass  # table missing/corrupt -> fall through and (re)build

    # ensure schema
    db_path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, IG_CONTROL_TOWER_DB_PATH=str(db_path))
    if INIT_DB.exists():
        subprocess.run([sys.executable, str(INIT_DB)], env=env, check=True)
    else:
        print(f"WARNING: {INIT_DB} not found — assuming the DB schema already exists.")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")

    # 1. generic_opportunities (must go first — analyses reference them)
    gf = export_dir / "generic_opportunities.json"
    g = json.loads(gf.read_text(encoding="utf-8")) if gf.exists() else []
    ng = upsert(conn, "generic_opportunities", "opportunity_id", g)

    # 2. company_profiles
    pf = export_dir / "company_profiles.json"
    p = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else []
    npf = upsert(conn, "company_profiles", "company_slug", p)

    # 3. company_analyses (per-company files)
    na = 0
    adir = export_dir / "company_analyses"
    if adir.exists():
        for f in sorted(adir.glob("*.json")):
            recs = json.loads(f.read_text(encoding="utf-8"))
            na += upsert(conn, "company_analyses", "analysis_id", recs, transform=resolve_fk)

    conn.commit()
    conn.close()

    # metrics
    msrc = export_dir.parent / "metrics" / "ig-control-tower-metrics.json"
    if msrc.exists():
        DEFAULT_METRICS.parent.mkdir(parents=True, exist_ok=True)
        if not DEFAULT_METRICS.exists():
            DEFAULT_METRICS.write_text(msrc.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"Imported into {db_path}")
    print(f"  generic_opportunities upserted: {ng}")
    print(f"  company_profiles upserted:      {npf}")
    print(f"  company_analyses upserted:      {na}")


if __name__ == "__main__":
    main()
