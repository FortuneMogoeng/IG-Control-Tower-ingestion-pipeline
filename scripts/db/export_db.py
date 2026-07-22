#!/usr/bin/env python3
"""Export the local IG Control Tower SQLite database to git-mergeable JSON.

This produces the canonical, versioned "database of opportunities" that the team
shares via the repo (no binary .db is committed). Run it after a Control Tower run
(P8 does this automatically) and commit the changed files.

Usage:
    python export_db.py [out_dir] [db_path]

Defaults:
    out_dir = <plugin>/data/db_export   (i.e. the dir next to this script's skills/.. parent)
    db_path = $IG_CONTROL_TOWER_DB_PATH  or  ~/.claude/data/ig-control-tower.db

Outputs (under out_dir):
    company_profiles.json
    generic_opportunities.json
    company_analyses/<company-slug>.json   (one per company)
    _manifest.json
And copies the metrics file -> <out_dir>/../metrics/ig-control-tower-metrics.json
"""
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Standalone layout (this repo): scripts/db/export_db.py -> repo root is parents[2].
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data" / "db_export"
DEFAULT_DB = Path(os.environ.get("IG_CONTROL_TOWER_DB_PATH",
                                 Path.home() / ".claude" / "data" / "ig-control-tower.db"))
DEFAULT_METRICS = Path(os.environ.get("IG_CONTROL_TOWER_METRICS_PATH",
                                      Path.home() / ".claude" / "data" / "ig-control-tower-metrics.json"))

# columns we never round-trip (auto-generated)
DROP_COLS = {"id", "created_at", "updated_at"}


def slugify(s):
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown"


def rows(conn, table):
    cur = conn.execute(f"SELECT * FROM {table}")
    cols = [c[0] for c in cur.description]
    return cols, [dict(zip(cols, r)) for r in cur.fetchall()]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    out_dir = Path(args[0]) if len(args) >= 1 else DEFAULT_OUT
    db_path = Path(args[1]) if len(args) >= 2 else DEFAULT_DB
    if not db_path.exists():
        print(f"ERROR: SQLite DB not found at {db_path}")
        sys.exit(1)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "company_analyses").mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))

    # generic_opportunities -> single file, keyed by opportunity_id; map int id -> opportunity_id
    g_cols, g_rows = rows(conn, "generic_opportunities")
    id_to_oppid = {r["id"]: r.get("opportunity_id") for r in g_rows}
    g_out = []
    for r in sorted(g_rows, key=lambda x: (str(x.get("opportunity_id") or ""), x.get("id") or 0)):
        g_out.append({k: v for k, v in r.items() if k not in DROP_COLS})
    (out_dir / "generic_opportunities.json").write_text(
        json.dumps(g_out, ensure_ascii=False, indent=2), encoding="utf-8")

    # company_profiles -> single file, keyed by company_slug
    p_cols, p_rows = rows(conn, "company_profiles")
    p_out = [{k: v for k, v in r.items() if k not in DROP_COLS}
             for r in sorted(p_rows, key=lambda x: str(x.get("company_slug") or ""))]
    (out_dir / "company_profiles.json").write_text(
        json.dumps(p_out, ensure_ascii=False, indent=2), encoding="utf-8")

    # company_analyses -> one file per company_slug; replace FK rowid with the string opportunity_id
    a_cols, a_rows = rows(conn, "company_analyses")
    by_slug = {}
    for r in a_rows:
        rec = {k: v for k, v in r.items() if k not in DROP_COLS}
        # resolve FK -> string
        goid = rec.pop("generic_opportunity_id", None)
        rec["generic_opportunity_opportunity_id"] = id_to_oppid.get(goid)
        slug = slugify(r.get("company_slug") or r.get("company_name"))
        by_slug.setdefault(slug, []).append(rec)
    # remove stale per-company files for slugs no longer present
    for f in (out_dir / "company_analyses").glob("*.json"):
        if f.stem not in by_slug:
            f.unlink()
    for slug, recs in by_slug.items():
        recs.sort(key=lambda x: str(x.get("analysis_id") or ""))
        (out_dir / "company_analyses" / f"{slug}.json").write_text(
            json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")

    # metrics
    metrics_out_dir = out_dir.parent / "metrics"
    metrics_out_dir.mkdir(parents=True, exist_ok=True)
    if DEFAULT_METRICS.exists():
        (metrics_out_dir / "ig-control-tower-metrics.json").write_text(
            DEFAULT_METRICS.read_text(encoding="utf-8"), encoding="utf-8")

    manifest = {
        "source_db": str(db_path),
        "exported_tables": {
            "generic_opportunities": len(g_out),
            "company_profiles": len(p_out),
            "company_analyses": sum(len(v) for v in by_slug.values()),
        },
        "companies": sorted(by_slug.keys()),
        "schema_columns": {
            "generic_opportunities": g_cols,
            "company_profiles": p_cols,
            "company_analyses": a_cols,
        },
    }
    (out_dir / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()

    print(f"Exported -> {out_dir}")
    print(f"  generic_opportunities: {len(g_out)}")
    print(f"  company_profiles:      {len(p_out)}")
    print(f"  company_analyses:      {manifest['exported_tables']['company_analyses']}  ({len(by_slug)} companies)")
    if DEFAULT_METRICS.exists():
        print(f"  metrics:               copied to {metrics_out_dir / 'ig-control-tower-metrics.json'}")


if __name__ == "__main__":
    main()
