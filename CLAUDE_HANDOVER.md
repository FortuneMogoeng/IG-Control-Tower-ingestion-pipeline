# IG Control Tower — Claude Agent Handover
**Written:** 13 July 2026  
**Author:** Fortune Mogoeng · Fortune@inferencegroup.com  
**Returning:** 21 July 2026  
**Read this first.** This document gives a new Claude Code session everything it needs to continue the work without asking Fortune.

---

## Who You Are Working With

**Fortune Mogoeng** — Inference Group consultant building the IG Control Tower pipeline.  
- Email: Fortune@inferencegroup.com  
- GitHub: FortuneMogoeng  
- Working directory: `C:\Users\FORTUNE\OneDrive - TCN Capital\Control Tower`  
- British English. No em dashes. No emojis. Terse responses preferred.

**Team:**
- Richard — CEO
- Karin — Business partner
- Wei — Project manager (primary technical contact)
- Jess — Has write access to `Inference-Group/ig-plugins` main branch

**Active clients:**
- Downing LLP — ongoing
- VMO2 (Watson Jones) — new, started July 2026

---

## What This Project Is

The **IG Control Tower** is a Claude Code plugin that turns client meeting files into a scored, prioritised AI opportunity report. It has two modes:

1. `/ig-control-tower:control-tower <Company>` — top-down prospecting (sector research, no prior engagement)
2. `/ig-ai-opportunity-discovery <Company> <Project>` — evidence-grounded delivery (meeting notes, Q&A sessions, transcripts)

The pipeline has 13 stages. Each stage is a sub-skill. Everything runs locally via Claude Code CLI. The plugin repo is at `Inference-Group/ig-plugins` (private).

**Fortune's role:** Building the ingestion layer and infrastructure (Path A done, Path B next). She does not have write access to push directly to `Inference-Group/ig-plugins:main` — Jess merges her branches.

---

## Current State — 13 July 2026

### What Is Live and Stable

| Component | Status |
|-----------|--------|
| Path A — local file ingestion | **Live and stable** |
| `parse_vtt.py` v1.2 | Deployed — Teams/Zoom/Fireflies VTT parsing |
| `_auto_ingest.py` v1.1 | Deployed — Stage 0 auto-parse wrapper |
| Azure Table Storage | Live — 1,791 opportunities, 1,951 analyses |
| Notion sync | Live — Company DB, Meeting Notes, People DB |
| SQLite local DB | Live — 1,791 generic_opportunities loaded at session start |
| FCA audit manifest | Live — `_ingestion_manifest.json` per run |
| Smoke tests Groups 1–4 | Passing — 28 tests |

### What Is Pending

| Component | Status | Effort |
|-----------|--------|--------|
| Merge ingestion PR to `ig-plugins` main | Waiting on Jess | 30 min |
| Path B — Azure Function trigger | Next sprint | ~1 day |
| Smoke tests Groups 5–7 | Blocked on Path B | ~2 hrs after Path B |
| Path C — Azure AI Search / RAG | Future | ~1 week, triggers at 5th client |

---

## The Immediate Next Task

### 1. Chase the merge

The ingestion branch is at:
`https://github.com/FortuneMogoeng/IG-Control-Tower-ingestion-pipeline`

Jess needs to apply it to `Inference-Group/ig-plugins`. Everything is in `MERGE_GUIDE.md` in that repo. If Jess hasn't done it by the time Fortune returns on 21 July, follow up with her.

### 2. Build Path B — Azure Function

Once merged, the next task is deploying the Azure document-parser function. Full spec is in:
- `JULY\HANDOVER-13-July-2026.md` — Part 3
- `C:\Users\FORTUNE\OneDrive - TCN Capital\Control Tower\WORK_PLAN.md`

**What to build:**
- Azure Function App `document-parser-fn` (Python 3.11, Consumption plan)
- Event Grid system topic on the existing storage account — filter: `BlobCreated`, extension allowlist `.vtt .pdf .xlsx .docx .pptx .md .txt`
- `intake-{client-slug}` and `processed-{client-slug}` blob containers (one per client)
- `_download_azure_fragments()` in `_auto_ingest.py` — already stubbed, needs deploying
- Blob access logging → Log Analytics (zero code, FCA requirement)

All in `rg-ig-control-tower`, UK South. Cost: ~£2/month.

Connection string: `AZURE_STORAGE_CONNECTION_STRING` — already in use by `db_sync.py`.

---

## Key File Locations

```
C:\Users\FORTUNE\OneDrive - TCN Capital\Control Tower\
│
├── CLAUDE_HANDOVER.md              ← this file
├── WORK_PLAN.md                    ← Path B + Path C spec
├── MERGE_GUIDE.md                  ← instructions for Jess
├── PATCHES.md                      ← exact SKILL.md + parse_any.py patches
├── README.md                       ← plain-English pipeline overview
├── scripts\                        ← v1.2 ingestion scripts (source of truth)
│   ├── _auto_ingest.py
│   └── parsers\
│       ├── parse_vtt.py            ← v1.2 (13 July fix)
│       ├── parse_any.py
│       ├── parse_pdf.py
│       ├── parse_word.py
│       ├── parse_excel.py
│       └── parse_pptx.py
├── tests\
│   ├── fixtures\                   ← real-teams.vtt, zoom-format.vtt, etc.
│   └── TEST_RESULTS.md             ← 5/5 PASS on 13 July
├── docs\
│   └── ingestion-architecture.md  ← formal architecture spec v2.0
│
├── JULY\
│   ├── HANDOVER-13-July-2026.md   ← full technical handover (read this for detail)
│   ├── OOO-email-draft.md         ← email sent to Wei (BCC Richard, Karin)
│   ├── 10 July 2026\scripts\      ← v1.2 source scripts
│   └── Complete arch\             ← HTML architecture diagrams
│
├── CLONE igplugin--FORTUNE\ig-plugins\
│   └── feature/ingestion-pipeline-v1.2  ← committed, ready (Fortune can't push to ig-plugins)
│
└── ig-plugins\                    ← main plugin repo files
    └── (see CLONE above for the active work)
```

---

## Repo Structure (ig-plugins)

```
Inference-Group/ig-plugins (private)
  plugins/ig-control-tower/
    skills/
      ig-ai-opportunity-discovery/    ← the 13-stage delivery pipeline
        SKILL.md                      ← Stage 0 was patched (auto-ingest block)
        scripts/
          _auto_ingest.py             ← NEW — Stage 0 wrapper
          parsers/
            parse_vtt.py              ← NEW — v1.2
            parse_any.py              ← UPDATED — .vtt added
            parse_pdf.py              ← NEW
            parse_word.py             ← NEW
            parse_excel.py            ← NEW
            parse_pptx.py             ← NEW
      ig-control-tower/               ← 9-phase prospecting pipeline
      ig-meeting-discovery/           ← Stage 1
      ig-strategy-discovery/          ← Stage 2
      ig-data-discovery/              ← Stage 3
      ig-tech-discovery/              ← Stage 4
      ig-risk-discovery/              ← Stage 5
      ig-opportunity-extraction/      ← Stage A
      ig-opportunity-assessment/      ← Stage B/C
      ig-opportunity-value-analysis/  ← Stage D/E
      ig-solution-design/             ← Stage F
      ig-opportunity-red-team/        ← Stage G
      ig-opportunity-to-notion/       ← Notion write-back
      ig-ai-roadmap/                  ← roadmap generation
    scripts/                          ← db_sync.py, import_db.py, export_db.py
    data/db_export/                   ← canonical JSON opportunity database
```

---

## Environment Variables

Never hardcoded. Load from `.env` at the repo root.

| Variable | Purpose | Required for |
|----------|---------|--------------|
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Table + Blob | Path A (sync), Path B (trigger) |
| `NOTION_COMPANY_DB_ID` | Notion company database | All stages |
| `NOTION_NOTES_DB_ID` | Notion meeting notes | Stage 0, Stage 1 |
| `NOTION_PEOPLE_DB_ID` | Notion contacts | Stage 3 |
| `IG_CONTROL_TOWER_DB_PATH` | SQLite path override | Optional — defaults to `~/.claude/data/ig-control-tower.db` |

---

## Common Commands

```bash
# Test the VTT parser (no Azure/Notion needed)
python scripts/parsers/parse_vtt.py tests/fixtures/real-teams.vtt

# Test auto-ingest wrapper
mkdir test-run\Evidence
copy tests\fixtures\real-teams.vtt test-run\Evidence\
python scripts/_auto_ingest.py .\test-run --client-slug test

# Run the full discovery pipeline
/ig-ai-opportunity-discovery "Downing LLP" "Q3 Discovery" --resume

# Sync Azure Table Storage
python plugins/ig-control-tower/scripts/db_sync.py push
python plugins/ig-control-tower/scripts/db_sync.py pull

# Check DB state (SQLite)
python -c "import sqlite3; c=sqlite3.connect('/Users/FORTUNE/.claude/data/ig-control-tower.db'); print(c.execute('SELECT COUNT(*) FROM generic_opportunities').fetchone())"
```

---

## Decisions Already Made — Do Not Revisit

| Decision | Reason |
|----------|--------|
| Deterministic Python scripts for parsing (not AI) | FCA requires traceable provenance. sha256 fragment IDs are verifiable; AI extraction is not. Python parsing is also free. |
| Three-path ingestion (A local → B Azure → C search) | Each path is additive. Agents never know which path is active. |
| Fragment schema frozen at 13 fields | Changing it invalidates all existing IDs in Azure. Do not add/remove required fields. |
| `fragment_id` = sha256(filename+offset)[:16] | Stable across re-ingestion. Do not change the algorithm. |
| No Fivetran/Airbyte | Neither handles VTT natively; both cost £300+/month; evidence is documents not DB tables. |
| No Notion for long-term storage | Being phased out in favour of SharePoint + Azure. Do not add new Notion dependencies. |
| Azure region: UK South (except SWA = westeurope) | SWA is not offered in UK South. Do not "fix" this. |
| Power BI Embedded A2 (~£280/mo) is a hard requirement | FCA reporting needs it. Do not substitute with a free tier. |

---

## Open Questions (as of 13 July)

| Question | Owner | Notes |
|----------|-------|-------|
| Did VMO2 first pipeline run succeed? | Fortune (check on return 21 July) | Should have run week of 7 July |
| Azure subscription access for Path B? | Wei / infra owner | Needed before Path B deployment |
| When does the 5th active client arrive? (triggers Path C) | Fortune + Richard | Currently 2 active clients |
| Power BI dashboard over GenericOpportunities table | Backlog | Unassigned |

---

## What Not to Do

- Do not push directly to `Inference-Group/ig-plugins:main` — Fortune cannot, Jess must review and merge
- Do not change the fragment schema without updating all parsers and smoke tests
- Do not add new Notion DB dependencies — Notion is being phased out
- Do not suggest keeping Notion or a CLI-only approach as the long-term architecture
- Do not run `git add -A` or `git add .` in the CLONE folder — stage only the specific ingestion files
- Do not commit `.env` files, `notion_toke.env`, or any secrets
- Do not use the `--no-verify` flag on git commits

---

## Architecture in One Diagram

```
Evidence/ (local files)  OR  Azure Blob intake-{client} (Path B)
         │
         ▼
  _auto_ingest.py  ←  Stage 0 wrapper
         │
         ├── parse_vtt.py    → transcript → fragments (2-min speaker windows)
         ├── parse_pdf.py    → PDF → fragments (page-by-page)
         ├── parse_xlsx.py   → XLSX → fragments (sheet-by-sheet)
         ├── parse_word.py   → DOCX → fragments (heading hierarchy)
         └── parse_pptx.py   → PPTX → fragments (slide-by-slide)
                                    │
                                    ▼
                    fragments.jsonl + _ingestion_manifest.json (FCA)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             Stages 1–5        Stages A–G      Azure Table
       (evidence gathering)  (analysis +      Storage (live)
                              delivery)
                    │               │
                    ▼               ▼
              Notion sync      SQLite DB
         (canvases, notes,   (1,791 opps)
          people profiles)
```

**Cost:** Path A ~£0.20/mo · Path B ~£2/mo · Path C ~£160-200/mo

---

*IG Control Tower · Agent Handover · 13 July 2026 · FCA-regulated — handle with care*
