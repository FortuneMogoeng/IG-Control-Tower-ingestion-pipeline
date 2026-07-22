# scripts/db — local SQLite <-> JSON <-> Azure

Consolidated into this repo on 22 July 2026 (pivot: this repo is canonical).
These are the same scripts as the plugin, patched only for the standalone layout
(`init_db.py` co-located here; export dir defaults to `<repo>/data/db_export`).

| Script | Purpose |
|--------|---------|
| `init_db.py` | Create the SQLite schema (idempotent, `IF NOT EXISTS`). |
| `import_db.py` | JSON export -> local SQLite (UPSERT by natural key). Runs `init_db` first. |
| `export_db.py` | local SQLite -> git-mergeable JSON (per-company files + manifest). |
| `db_sync.py` | local SQLite <-> Azure Table Storage (`push` / `pull` / `status`). |
| `_envload.py` | Zero-dependency `.env` loader used by the above. |

## Usage

```bash
# Rebuild the local DB schema
python scripts/db/init_db.py

# Export the live DB to JSON (default out: <repo>/data/db_export)
python scripts/db/export_db.py [out_dir] [db_path]

# Import JSON back into SQLite
python scripts/db/import_db.py [export_dir] [db_path]
python scripts/db/import_db.py --if-missing   # no-op if DB already populated (hook-friendly)

# Azure Table mirror (needs a connection string in .env)
python scripts/db/db_sync.py status
python scripts/db/db_sync.py push
python scripts/db/db_sync.py pull
```

## Config

- DB path: `IG_CONTROL_TOWER_DB_PATH` or `~/.claude/data/ig-control-tower.db`
- Azure: `AZURE_STORAGE_CONNECTION_STRING` (or `AZURE_STORAGE_ACCOUNT` + `AZURE_STORAGE_TABLE_SAS`)
- `db_sync.py` requires `pip install azure-data-tables`.

`data/db_export/` is not committed here (it is the plugin's canonical store);
`export_db.py` regenerates it from the live SQLite on demand.
