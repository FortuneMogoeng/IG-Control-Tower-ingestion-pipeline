# IG Control Tower — Claude Agent Handover
**Written:** 13 July 2026 · **Revised:** 22 July 2026
**Author:** Fortune Mogoeng · Fortune@inferencegroup.com
**Read this first.** This gives a new Claude Code session everything it needs to continue without asking Fortune.

---

## Pivot — 22 July 2026 (read before anything else)

Three decisions were made on 22 July that override the original plan in this repo. Do not act on older instructions that contradict them.

1. **This repo is the canonical solution.** Working directory `C:\Users\FORTUNE\OneDrive - TCN Capital\Control Tower` → remote `github.com/FortuneMogoeng/IG-Control-Tower-ingestion-pipeline` (branch `main`). All new work is built here.
2. **The Inference-Group / Jess merge track is dropped.** No dependency on `Inference-Group/ig-plugins`. Do not chase a merge. `MERGE_GUIDE.md` and `PATCHES.md` are superseded and kept only for history.
3. **VMO2 first delivery run is parked for Wei.** No evidence-grounded run exists locally (verified 22 July: no Evidence/, Meeting-Notes/, manifest, or progress file for VMO2). The VMO2 rows in SQLite are the 9 July prospecting seed, not a delivery run. Likely ran on another laptop or not at all. This machine has no live Azure creds, so it could not be confirmed via Azure/Notion.

Scope of this repo (agreed 22 July): the **ingestion + Azure infra layer** (Paths A/B/C, parsers, manifests). The 13-stage analytical plugin is out of scope unless that changes.

---

## Who You Are Working With

**Fortune Mogoeng** — Inference Group consultant, owns this pipeline.
- British English. No em dashes. No emojis. Terse responses preferred.

**Team:**
- Richard — CEO
- Karin — Business partner
- Wei — Project manager, primary technical contact, owns Azure access
- Jess — Held write access to `Inference-Group/ig-plugins` (no longer in the critical path after the 22 July pivot)

**Active clients:** Downing LLP (ongoing) · VMO2 / Virgin Media O2 (Watson Jones, new July 2026)

---

## What This Project Is

The ingestion layer that turns raw client files (transcripts, PDFs, decks, sheets) into clean, FCA-traceable fragments the downstream Control Tower pipeline consumes. Parsing is deterministic Python only — no Claude in the parse path.

Three additive paths:
- **Path A — local.** Drop files in `Evidence/`, `_auto_ingest.py` parses them into `Meeting-Notes/`. **Live and stable.**
- **Path B — Azure.** Upload to `intake-{slug}/` blob container, an Azure Function parses remotely into `processed-{slug}/`. **Scaffolded, blocked on Azure access.**
- **Path C — semantic.** Azure AI Search index over all fragments. **Future, triggers at 5th active client.**

---

## Current State — 22 July 2026

### Live and stable
| Component | Status |
|-----------|--------|
| Path A — local ingestion | Live |
| Parsers: vtt, pdf, word, excel, pptx, md/txt | All present and loading (pdf/word/excel/pptx pulled in 22 July) |
| `parse_vtt.py` v1.2 | sha256 fragment ids, Teams/Zoom/Fireflies |
| `_auto_ingest.py` | Stage 0 wrapper, includes Path B client-side downloader |
| Azure Table Storage | Live (per db_sync) — not reachable from this machine (no .env) |
| SQLite local DB | 1,791 generic_opportunities loaded at session start |

### Pending
| Component | Status | Blocker |
|-----------|--------|---------|
| Path B — Azure Function deploy | Scaffolded in `azure/document-parser-fn/` | Azure subscription access (Wei) |
| Smoke tests Groups 6-7 | To write | Best written now, run after Path B deploys |
| Path C — Azure AI Search | Future | 5th active client |
| VMO2 first run confirmation | Parked | Wei / other consultant |

---

## The Immediate Next Task

**Deploy Path B once Azure access is granted.** The code is ready:
- `azure/document-parser-fn/function_app.py` — Event Grid triggered, reuses `scripts/parsers` unchanged, writes `processed-{slug}/evidence/{stem}_fragments.jsonl`.
- Deploy steps (`az` CLI, Event Grid wiring, containers, FCA blob logging) are in `azure/document-parser-fn/README.md`.
- The client side (`_download_azure_fragments` in `_auto_ingest.py`) is already implemented.

Until access lands, work the unblocked items: write smoke tests Groups 6-7, optionally consolidate `db_sync`/`import_db`/`export_db` into this repo, or start the Power BI dashboard.

---

## Key File Locations

```
Control Tower\  (= this repo, canonical)
├── CLAUDE_HANDOVER.md              ← this file
├── WORK_PLAN.md                    ← Path B + Path C spec (revised 22 July)
├── README.md                       ← plain-English pipeline overview
├── MERGE_GUIDE.md                  ← SUPERSEDED (history only)
├── PATCHES.md                      ← SUPERSEDED (history only)
├── scripts\
│   ├── _auto_ingest.py             ← Stage 0 wrapper + Path B client downloader
│   └── parsers\
│       ├── parse_any.py            ← dispatcher (PARSERS dict)
│       ├── parse_vtt.py            ← v1.2, sha256 ids
│       ├── parse_pdf.py  parse_word.py  parse_excel.py  parse_pptx.py
├── azure\document-parser-fn\       ← Path B Function (scaffolded 22 July)
│   ├── function_app.py  requirements.txt  host.json  README.md
├── tests\
│   ├── fixtures\                   ← real-teams.vtt, zoom-format.vtt, etc.
│   └── TEST_RESULTS.md
└── docs\ingestion-architecture.md
```

---

## Environment Variables

Load from `.env` at repo root (not present on this machine — Path A works without it).

| Variable | Purpose | Required for |
|----------|---------|--------------|
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Table + Blob | Path B (Function + client downloader) |
| `NOTION_*_DB_ID` | Notion databases | Downstream stages (Notion being phased out) |
| `IG_CONTROL_TOWER_DB_PATH` | SQLite path override | Optional |

---

## Common Commands

```bash
# Test the VTT parser (no Azure/Notion needed)
python scripts/parsers/parse_vtt.py tests/fixtures/real-teams.vtt

# Run the local auto-ingest over an Evidence/ folder
python scripts/_auto_ingest.py <project_dir> --client-slug <slug>

# Check DB state (SQLite)
python -c "import sqlite3; c=sqlite3.connect('C:/Users/FORTUNE/.claude/data/ig-control-tower.db'); print(c.execute('SELECT COUNT(*) FROM generic_opportunities').fetchone())"

# Deploy Path B (after Azure access) — see azure/document-parser-fn/README.md
```

---

## Decisions Already Made — Do Not Revisit

| Decision | Reason |
|----------|--------|
| This repo is canonical; no upstream merge | 22 July pivot |
| Deterministic Python parsers (not AI) | FCA needs traceable provenance; sha256 ids are verifiable; free to run |
| Three-path ingestion (A local → B Azure → C search) | Each path is additive; agents never know which path is active |
| Fragment schema frozen | Changing it invalidates existing ids in Azure |
| `fragment_id` = sha256(source+offset)[:16] | Stable across re-ingestion |
| No Fivetran/Airbyte | Neither handles VTT; both cost £300+/month; evidence is documents not DB tables |
| Notion not for long-term storage | Being phased out for SharePoint + Azure |
| Azure region UK South (SWA = westeurope exception) | SWA not offered in UK South |
| Power BI Embedded A2 (~£280/mo) | FCA reporting requirement |

Known inconsistency to reconcile: `parse_any.parse_md_txt` still uses uuid4 ids (6-field schema); `_auto_ingest._parse_plain_text` and the Path B Function use the canonical sha256 schema. Path A and Path B are consistent with each other; `parse_any`'s standalone md/txt path is the outlier.

---

## What Not to Do

- Do not change the fragment schema without updating all parsers and smoke tests
- Do not add new Notion DB dependencies — Notion is being phased out
- Do not commit `.env`, `notion_toke.env`, or any secrets
- Do not use `--no-verify` on git commits
- Do not commit the vendored `azure/**/parsers/` build artefact (gitignored)

---

## Architecture in One Diagram

```
Evidence/ (local, Path A)   OR   Azure Blob intake-{slug}/ (Path B)
        │                                │
        │                        document-parser-fn (Azure Function)
        │                                │  writes processed-{slug}/evidence/*.jsonl
        ▼                                ▼
  _auto_ingest.py  ──────────────  _download_azure_fragments()
        │
        ├── parse_vtt / pdf / word / excel / pptx / md-txt
        ▼
  fragments (sha256 ids) → Meeting-Notes/ → downstream Control Tower stages
```

**Cost:** Path A ~£0.20/mo · Path B ~£2/mo · Path C ~£160-200/mo

---

*IG Control Tower · Agent Handover · revised 22 July 2026 · FCA-regulated — handle with care*
