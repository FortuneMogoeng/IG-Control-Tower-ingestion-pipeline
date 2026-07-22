#!/usr/bin/env python3
"""Mirror the local IG Control Tower SQLite DB to/from a shared Azure Table Storage account.

This is the "live shared database" path: every teammate's run `push`es its new rows to the
same Azure Storage account, so the owner (and everyone) sees them without a PR. The Control
Tower skill itself keeps using local SQLite as its working engine — this script is the only
thing that talks to Azure.

Usage:
    python db_sync.py push        # local SQLite  -> Azure Table Storage
    python db_sync.py pull        # Azure Table Storage -> local SQLite (ensures schema first)
    python db_sync.py status      # print connectivity + row/entity counts

Auth (from environment / .env — never committed):
    AZURE_STORAGE_CONNECTION_STRING                  (preferred), OR
    AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_TABLE_SAS  (a SAS scoped to the Table service)
DB path:
    $IG_CONTROL_TOWER_DB_PATH  or  ~/.claude/data/ig-control-tower.db

Tables (auto-created): GenericOpportunities (PK=dimension code, RK=opportunity_id),
CompanyAnalyses (PK=company_slug, RK=analysis_id), CompanyProfiles (PK="profile", RK=company_slug).
JSON-array/object columns are stored as JSON strings.

Requires:  pip install azure-data-tables
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

# Standalone layout (this repo): init_db.py sits next to this script in scripts/db/.
INIT_DB = Path(__file__).resolve().parent / "init_db.py"
DB_PATH = Path(os.environ.get("IG_CONTROL_TOWER_DB_PATH",
                              Path.home() / ".claude" / "data" / "ig-control-tower.db"))

DIM_CODE = {"Efficiency & Productivity": "EFF", "Revenue & Growth": "REV", "Customer & Client": "CUS",
            "A": "EFF", "B": "REV", "C": "CUS"}

# columns that hold JSON text in the SQLite schema (so we json.loads them on pull, for cleanliness)
JSON_COLS = {"applicable_sectors", "applicable_divisions", "technology_types", "platforms",
             "integrations", "additional_evidence", "sources", "quantified_benefits",
             "qualitative_benefits", "implementation_phases", "key_delivery_components", "risks",
             "regulatory_flags", "required_approvals", "dependencies", "regions", "tech_stack",
             "departments", "competitors", "brand_colors"}
DROP_COLS = {"id", "created_at", "updated_at"}

import re as _re
import math as _math
# Azure Table PartitionKey/RowKey may not contain  /  \  #  ?  or control chars, and may not be empty.
_BAD_KEY = _re.compile(r"[/\\#?\t\n\r\x00-\x1f\x7f]")


def _safe_key(v):
    s = "" if v is None else str(v)
    s = _BAD_KEY.sub("_", s).strip()
    return s or "_"


def _safe_val(v):
    """Drop values Azure Tables won't accept (NaN / Infinity)."""
    if isinstance(v, float) and not _math.isfinite(v):
        return None
    return v


def get_service_client():
    try:
        from azure.data.tables import TableServiceClient  # noqa
    except ImportError:
        print("ERROR: the 'azure-data-tables' package is required.  pip install azure-data-tables")
        sys.exit(2)
    from azure.data.tables import TableServiceClient
    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if conn:
        return TableServiceClient.from_connection_string(conn)
    acct = os.environ.get("AZURE_STORAGE_ACCOUNT")
    sas = os.environ.get("AZURE_STORAGE_TABLE_SAS")
    if acct and sas:
        url = f"https://{acct}.table.core.windows.net"
        cred = sas if sas.startswith("?") else f"?{sas}"
        return TableServiceClient(endpoint=url + cred)
    print("ERROR: set AZURE_STORAGE_CONNECTION_STRING, or AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_TABLE_SAS, in your .env")
    sys.exit(2)


def table(svc, name):
    try:
        svc.create_table_if_not_exists(name)
    except Exception:
        pass
    return svc.get_table_client(name)


def to_entity(pk, rk, row):
    ent = {"PartitionKey": str(pk), "RowKey": str(rk)}
    for k, v in row.items():
        if k in DROP_COLS:
            continue
        v = _safe_val(v)
        if v is None:
            continue
        if isinstance(v, (dict, list)):
            ent[k] = json.dumps(v, ensure_ascii=False)
        elif isinstance(v, bool):
            ent[k] = v
        elif isinstance(v, (int, float, str)):
            ent[k] = v
        else:
            ent[k] = str(v)
    return ent


def from_entity(ent):
    row = {}
    for k, v in ent.items():
        if k in ("PartitionKey", "RowKey") or k.startswith("odata.") or k == "Timestamp":
            continue
        if k in JSON_COLS and isinstance(v, str):
            try:
                row[k] = json.loads(v)
            except (ValueError, TypeError):
                row[k] = v
        else:
            row[k] = v
    return row


def sqlite_rows(conn, t):
    cur = conn.execute(f"SELECT * FROM {t}")
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def table_columns(conn, t):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]


def cmd_status(svc):
    conn = sqlite3.connect(str(DB_PATH)) if DB_PATH.exists() else None
    for t in ("GenericOpportunities", "CompanyAnalyses", "CompanyProfiles"):
        try:
            n = sum(1 for _ in table(svc, t).list_entities())
        except Exception as e:
            n = f"err: {e}"
        print(f"  azure {t}: {n}")
    if conn:
        for t in ("generic_opportunities", "company_analyses", "company_profiles"):
            try:
                print(f"  sqlite {t}: {conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0]}")
            except sqlite3.Error as e:
                print(f"  sqlite {t}: err: {e}")
        conn.close()
    else:
        print(f"  (no local DB at {DB_PATH})")


def cmd_push(svc):
    if not DB_PATH.exists():
        print(f"ERROR: local DB not found at {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    id_to_oppid = {r["id"]: r.get("opportunity_id") for r in sqlite_rows(conn, "generic_opportunities")}

    g = table(svc, "GenericOpportunities")
    ng = 0
    for r in sqlite_rows(conn, "generic_opportunities"):
        pk = _safe_key(DIM_CODE.get(r.get("dimension"), "GEN"))
        rk = _safe_key(r.get("opportunity_id") or f"row{r.get('id')}")
        g.upsert_entity(to_entity(pk, rk, r))
        ng += 1

    a = table(svc, "CompanyAnalyses")
    na = 0
    for r in sqlite_rows(conn, "company_analyses"):
        rr = dict(r)
        rr["generic_opportunity_opportunity_id"] = id_to_oppid.get(rr.pop("generic_opportunity_id", None))
        pk = _safe_key(rr.get("company_slug") or "unknown")
        rk = _safe_key(rr.get("analysis_id") or f"row{r.get('id')}")
        a.upsert_entity(to_entity(pk, rk, rr))
        na += 1

    p = table(svc, "CompanyProfiles")
    np_ = 0
    for r in sqlite_rows(conn, "company_profiles"):
        rk = _safe_key(r.get("company_slug") or "unknown")
        p.upsert_entity(to_entity("profile", rk, r))
        np_ += 1

    conn.close()
    print(f"Pushed -> Azure Table Storage:  generic_opportunities {ng}  ·  company_analyses {na}  ·  company_profiles {np_}")


def _ensure_schema():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, IG_CONTROL_TOWER_DB_PATH=str(DB_PATH))
    if INIT_DB.exists():
        subprocess.run([sys.executable, str(INIT_DB)], env=env, check=True)


def _upsert(conn, t, key_col, rows, transform=None):
    cols = set(table_columns(conn, t))
    n = 0
    for row in rows:
        if transform:
            row = transform(conn, dict(row))
        row = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
               for k, v in row.items() if k in cols}
        if not row.get(key_col):
            continue
        names = list(row.keys())
        ph = ",".join("?" for _ in names)
        upd = ",".join(f"{c}=excluded.{c}" for c in names if c != key_col)
        if "updated_at" in cols and "updated_at" not in names:
            upd += ", updated_at=CURRENT_TIMESTAMP"
        conn.execute(f"INSERT INTO {t} ({','.join(names)}) VALUES ({ph}) ON CONFLICT({key_col}) DO UPDATE SET {upd}",
                     [row[c] for c in names])
        n += 1
    return n


def cmd_pull(svc):
    _ensure_schema()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = OFF")

    g_rows = [from_entity(e) for e in table(svc, "GenericOpportunities").list_entities()]
    ng = _upsert(conn, "generic_opportunities", "opportunity_id", g_rows)

    p_rows = [from_entity(e) for e in table(svc, "CompanyProfiles").list_entities()]
    np_ = _upsert(conn, "company_profiles", "company_slug", p_rows)

    def resolve(c, row):
        oppid = row.pop("generic_opportunity_opportunity_id", None)
        if oppid:
            r = c.execute("SELECT id FROM generic_opportunities WHERE opportunity_id=?", (oppid,)).fetchone()
            row["generic_opportunity_id"] = r[0] if r else None
        return row

    a_rows = [from_entity(e) for e in table(svc, "CompanyAnalyses").list_entities()]
    na = _upsert(conn, "company_analyses", "analysis_id", a_rows, transform=resolve)

    conn.commit()
    conn.close()
    print(f"Pulled <- Azure Table Storage:  generic_opportunities {ng}  ·  company_analyses {na}  ·  company_profiles {np_}  (DB: {DB_PATH})")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("push", "pull", "status"):
        print(__doc__)
        sys.exit(1)
    svc = get_service_client()
    {"push": cmd_push, "pull": cmd_pull, "status": cmd_status}[sys.argv[1]](svc)


if __name__ == "__main__":
    main()
