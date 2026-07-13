# IG Control Tower — Handover Document
**Date:** 13 July 2026  
**Prepared by:** Fortune Mogoeng · Fortune@inferencegroup.com  
**Returning:** Monday 21 July 2026  
**Picking up from:** 11 July handover (`JULY\11 july\handover.md`)

---

## TL;DR — Where Things Stand

The ingestion pipeline (Path A) is **live, tested, and ready to merge**. Drop any supported file into an `Evidence/` folder, run the pipeline, and it parses everything automatically. 5/5 tests passed this morning including a real Teams call.

The **one action needed while Fortune is away:** someone with write access to `Inference-Group/ig-plugins` needs to merge one PR. Everything for that is at:

> `https://github.com/FortuneMogoeng/IG-Control-Tower-ingestion-pipeline`

---

## Part 1 — What Was Built (7–13 July)

### The Problem That Was Fixed

Before this sprint, dropping a Teams transcript, PDF, or Excel file into a project folder did nothing — the AI agents couldn't read those file formats directly. Consultants had to manually extract text and reformat it. This blocked VMO2 from running the pipeline on their first call recording.

### What Was Built

Three scripts + one edit. That is all that changed. Everything else in the pipeline is untouched.

| What | Where in repo | What it does |
|------|---------------|--------------|
| `parse_vtt.py` (new) | `scripts/parsers/` | Reads Teams, Zoom, Fireflies `.vtt` transcript files. Groups speaker turns into 2-minute windows. Assigns a stable ID to each fragment so duplicates are never created on re-runs. |
| `_auto_ingest.py` (new) | `scripts/` | Scans the `Evidence/` folder at Stage 0. Calls the right parser for each file type. Writes readable `.md` files into `Meeting-Notes/` where Stage 1 already looks. |
| `parse_any.py` (updated) | `scripts/parsers/` | One line added: `.vtt` now routes to `parse_vtt.py`. |
| `SKILL.md Stage 0` (edited) | `ig-ai-opportunity-discovery/` | 12 lines added after `init_project.py` — calls `_auto_ingest.py` before any agents run. |

**What stayed exactly the same:** All 19 skills, all 40+ agent prompts, all 8 discovery stages (1–5, A–G), Notion integration, Azure Table Storage sync, `_progress.json` resumability, both dashboards.

### Bug Found and Fixed Today (v1.2)

During the last-minute test run this morning, Teams VTT files with multi-line speaker turns left a stray `</v>` tag in fragment content. Root cause: the regex only stripped `</v>` from the opening `<v Speaker>text` line. When a speaker turn spanned multiple lines, subsequent lines weren't stripped.

Fix: one line added in `parse_vtt.py` — a `re.sub(r"</v>\s*$", "", line)` on continuation lines. All fixtures clean after the fix.

### What Is Live Right Now

| Component | Status | Detail |
|-----------|--------|--------|
| Path A — local file ingestion | Live and stable | VTT, PDF, XLSX, DOCX, PPTX all parsing |
| Azure Table Storage | Live | 1,791 opportunities, 1,951 analyses |
| Notion sync | Live | Company DB, Meeting Notes, People DB |
| SQLite local DB | Live | 1,791 opportunities loaded at session start |
| FCA audit manifest | Live | `_ingestion_manifest.json` on every run |
| Smoke tests Groups 1–4 | Passing | 28 tests — parser, schema, ingestion, stages |

### Test Results (13 July 2026)

All five tests passed using `parse_vtt.py v1.2`:

| Test | File | Fragments | Result |
|------|------|-----------|--------|
| Teams multi-line | `real-teams.vtt` | 6 | PASS |
| Zoom sub-hour (MM:SS) | `zoom-format.vtt` | 2 | PASS |
| Fireflies export | `fireflies-test.vtt` | 1 | PASS |
| String cue IDs | `string-cues.vtt` | 1 | PASS |
| Real meeting (Teams) | `AI Control Tower Catch Up.vtt` | 6 | PASS |

---

## Part 2 — The Merge (Action Required)

### What Needs to Happen

The feature branch is ready. One person with write access to `Inference-Group/ig-plugins` needs to:

1. **Fork the repo** — Fortune does not have write access to the main repo, so she pushed to her own fork at:  
   `https://github.com/FortuneMogoeng/ig-plugins/tree/feature/ingestion-pipeline-v1.2`

2. **Open a PR** — from `FortuneMogoeng/ig-plugins:feature/ingestion-pipeline-v1.2` into `Inference-Group/ig-plugins:main`

3. **Review the diff** — 8 files: 7 new scripts + 1 SKILL.md edit. The diff is clean (no deleted files, no changes to existing skills or prompts).

4. **Merge**

5. **Run a quick smoke test** (5 minutes):
   ```bash
   python plugins/ig-control-tower/skills/ig-ai-opportunity-discovery/scripts/parsers/parse_vtt.py \
     path/to/any-teams-call.vtt
   # Expected: JSON array with speaker-labelled content, no </v> tags, at least 1 fragment
   ```

**Risk assessment:** Low. These are new files added to an empty `parsers/` directory. The only change to an existing file is 12 lines added to `SKILL.md` Stage 0. No existing behaviour is removed or altered.

### File Map (for the reviewer)

```
ig-ai-opportunity-discovery/
├── SKILL.md                          ← 12 lines added to Stage 0
└── scripts/
    ├── _auto_ingest.py               ← NEW — Stage 0 wrapper
    └── parsers/
        ├── parse_vtt.py              ← NEW — transcript parser (v1.2)
        ├── parse_any.py              ← NEW — file-type dispatcher
        ├── parse_pdf.py              ← NEW — PDF parser
        ├── parse_word.py             ← NEW — DOCX parser
        ├── parse_excel.py            ← NEW — XLSX parser
        └── parse_pptx.py             ← NEW — PPTX parser
```

---

## Part 3 — What Comes Next (Path B)

### Overview

Path B moves file intake from Fortune's laptop to Azure Blob Storage. Any consultant on any machine can upload files and trigger the pipeline remotely.

**Estimated effort:** 1 working day.  
**Dependency:** Azure subscription access to create a Function App and Event Grid topic.

### What Needs to Be Built

**1. Azure Function — `document-parser`**  
Triggered by Azure Event Grid when a file lands in `intake-{client-slug}/` container. Downloads the file, calls the existing parser, writes fragments to `processed-{client-slug}/evidence/`. No new parsing code needed — reuses the same parsers from Path A.

**2. Azure Event Grid system topic**  
One system topic on the existing storage account. Filter: `BlobCreated` events, extension allowlist: `.vtt`, `.pdf`, `.xlsx`, `.docx`, `.pptx`, `.md`, `.txt`.

**3. Update `_auto_ingest.py`**  
Add `_download_azure_fragments()` function (already stubbed, just needs deploying). When `AZURE_STORAGE_CONNECTION_STRING` is set, it also checks Azure Blob for pre-processed fragments. Fully backward-compatible — Path A still works when no connection string is present.

**4. Enable Blob access logging**  
Diagnostic logging on the storage account to Log Analytics Workspace. Zero code. FCA requirement.

### Azure Resources Needed

All in `rg-ig-control-tower`, UK South:

| Resource | Name |
|----------|------|
| Blob containers | `intake-{client-slug}` (one per client) |
| Blob containers | `processed-{client-slug}` (one per client) |
| Event Grid system topic | On the existing storage account |
| Azure Function App | `document-parser-fn` (Python 3.11, Consumption plan) |
| Log Analytics Workspace | Existing or new |

**Cost:** ~£2/month additional.

### Smoke Tests for Path B

After deployment, run:
- Group 5 (Notion sync): 4 tests
- Group 6 (Azure Storage): 5 tests  
- Group 7 (Full E2E): 4 tests

Full spec: `WORK_PLAN.md` in the documentation repo, or `JULY\11 july\handover.md`.

---

## Part 4 — Key Files and Locations

### Where to Find Everything

```
C:\Users\FORTUNE\OneDrive - TCN Capital\Control Tower\
│
├── JULY\
│   ├── ingestion-architecture.md      ← Full architecture spec (v2.0)
│   ├── ingestion-handover.md          ← 8 July handover (deployment steps)
│   ├── 11 july\handover.md            ← 11 July handover (current state before today)
│   ├── HANDOVER-13-July-2026.md       ← This document
│   ├── OOO-email-draft.md             ← Email to send to the team
│   ├── 10 July 2026\
│   │   ├── scripts\                   ← v1.2 ingestion scripts (source of truth)
│   │   └── fixtures\                  ← VTT test files
│   └── Complete arch\                 ← HTML architecture diagrams
│
└── CLONE igplugin--FORTUNE\ig-plugins\
    └── (feature branch ready to push — see below)
```

### The Feature Branch

```
Repo: CLONE igplugin--FORTUNE\ig-plugins\
Branch: feature/ingestion-pipeline-v1.2
Remote target: https://github.com/FortuneMogoeng/ig-plugins.git
```

**To push (Fortune runs this after forking on GitHub):**
```bash
cd "C:\Users\FORTUNE\OneDrive - TCN Capital\Control Tower\CLONE igplugin--FORTUNE\ig-plugins"
git push -u origin feature/ingestion-pipeline-v1.2
```

Then open a PR at: `https://github.com/FortuneMogoeng/ig-plugins/compare/feature/ingestion-pipeline-v1.2`

---

## Part 5 — Environment Variables

All secrets are environment variables. Never hardcoded, never committed to git. Load from `.env` at the repo root.

| Variable | Purpose | Path A | Path B |
|----------|---------|--------|--------|
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Table + Blob access | Optional | Required |
| `NOTION_COMPANY_DB_ID` | Notion company database | Required | Required |
| `NOTION_NOTES_DB_ID` | Notion meeting notes database | Required | Required |
| `NOTION_PEOPLE_DB_ID` | Notion people/contacts database | Required | Required |

---

## Part 6 — How to Run the Pipeline

### Quick test (no Azure/Notion needed)

```bash
# Parse a VTT file standalone
python scripts/parsers/parse_vtt.py path/to/meeting.vtt

# Run auto-ingest on a test folder
mkdir test-run\Evidence
copy path\to\meeting.vtt test-run\Evidence\
python scripts/_auto_ingest.py .\test-run --client-slug test-client
# Check: test-run\Meeting-Notes\ should contain *_parsed.md
```

### Full pipeline run

```
/ig-ai-opportunity-discovery "Downing LLP" "Q3 Discovery" --resume
```

Drop files in `Evidence/` before running Stage 0 and they will be ingested automatically.

---

## Part 7 — Decisions That Are Already Made

These are locked. Do not revisit without a full team discussion and an ADR.

| Decision | Reason |
|----------|--------|
| Deterministic scripts (not AI) for parsing | FCA requires traceable provenance. `sha256(file+offset)` fragment IDs are verifiable; AI extraction is not. Cost: Python is free; Claude API for 100 PDF pages ≈ £2. |
| Three-path architecture | Each path is additive. Path A ships immediately. Path B adds cloud. Path C adds search. Agents never know which path is active. |
| Fragment schema frozen (13 fields) | Changing it invalidates all existing IDs in Azure Table Storage. Do not add/remove required fields without updating all parsers and smoke tests. |
| `fragment_id` = sha256(filename+offset)[:16] | Stable across re-ingestion. FCA-verifiable. Do not change the algorithm. |

---

## Part 8 — Outstanding Items

| Item | Status | Action |
|------|--------|--------|
| Merge ingestion PR to main | Pending | Person with write access to ig-plugins |
| VMO2 first pipeline run confirmation | Unknown | Fortune to confirm on return (21 July) |
| Azure subscription access for Path B | Needs confirmation | Team lead / infra owner |
| Smoke tests Groups 5–7 | Blocked on Path B deploy | Engineering after Path B |
| Power BI dashboard over GenericOpportunities | Backlog | Unassigned |
| Path C (semantic search) trigger | Unscheduled — triggers at 5th active client | Fortune / leadership |

---

## Glossary (for non-technical readers)

**Fragment** — A structured chunk of text extracted from a source file. One page of a PDF becomes one fragment. One 2-minute window of a meeting transcript becomes one fragment. Each has a stable ID, source reference, and content.

**Evidence/** — A folder inside each client engagement project. Drop any supported file here and the pipeline reads it automatically.

**Meeting-Notes/** — The folder Stage 1 reads to find content for analysis. `_auto_ingest.py` writes here.

**Stage 0** — The first step of the pipeline. Sets up the project folder and now runs the auto-ingest before any AI agents start.

**Path A / Path B / Path C** — Three phases of the ingestion architecture. A = local files now. B = Azure cloud (next). C = semantic search (future).

**FCA** — Financial Conduct Authority. UK financial regulator. Data handling must be traceable, auditable, and retain records for 7 years.

**fragment_id** — A 16-character code that uniquely identifies a piece of evidence. Stable across re-runs. Links every AI-generated opportunity back to its source evidence.

---

*Inference Group Internal · 13 July 2026 · FCA-regulated — handle with care*
