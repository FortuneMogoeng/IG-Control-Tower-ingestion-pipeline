# IG Control Tower — Ingestion Pipeline v1.2

**Status:** Path A (local file ingestion) is live and stable as of 13 July 2026.  
**Prepared by:** Fortune Mogoeng · Fortune@inferencegroup.com  
**Last test run:** 13 July 2026 · 5/5 PASS

---

## What This Is (Plain English)

The IG Control Tower is a pipeline that turns raw client meeting files into a scored, prioritised AI opportunity report — automatically.

Before this work, consultants had to manually convert transcripts, PDFs, and slide decks into a format the pipeline could read. This took time and was error-prone.

**What we built:** A set of scripts that sit at the front of the pipeline. A consultant drops any supported file into a folder called `Evidence/`, runs the pipeline as normal, and the scripts handle the rest. The output lands in `Meeting-Notes/` where the AI agents already know to look. Nothing else in the pipeline changes.

---

## How the Pipeline Works (Step by Step)

```
1. Consultant drops files into Evidence/
   └── transcript.vtt  (Teams/Zoom/Fireflies recording)
   └── strategy-deck.pdf
   └── financial-model.xlsx

2. Pipeline starts (Stage 0)
   └── _auto_ingest.py runs automatically
       ├── parse_vtt.py  → turns transcript into readable fragments
       ├── parse_pdf.py  → turns PDF pages into fragments
       ├── parse_excel.py→ turns spreadsheet rows into fragments
       └── (and so on for each file type)

3. Fragments land in Meeting-Notes/
   └── transcript_parsed.md
   └── strategy-deck_parsed.md
   └── financial-model_parsed.md

4. AI agents run (Stages 1–13)
   └── They find the Meeting-Notes/ files automatically
   └── Extract opportunities, score them, write to Notion and Azure
   └── Produce the final report

5. Output
   └── Notion canvas with all opportunities
   └── Azure Table Storage (1,791 opportunities live as of 13 July)
   └── PDF report for the client
```

### What a "fragment" is

A fragment is a structured chunk of content from a source file. Think of it as a single paragraph that the AI agents can read and reason about. Each fragment records:
- What the content says
- Where it came from (which file, which page / slide / timestamp)
- Who said it (for transcripts)
- A unique ID that never changes even if the pipeline re-runs

This stable ID is important for FCA compliance — it means every opportunity can be traced back to an exact section of the original evidence.

---

## What's in This Repo

```
scripts/
  _auto_ingest.py          ← Stage 0 wrapper — runs all parsers automatically
  parsers/
    parse_vtt.py           ← NEW: transcript parser (Teams, Zoom, Fireflies)
    parse_any.py           ← UPDATED: routes files to the right parser

tests/
  fixtures/
    real-teams.vtt         ← Teams format test file
    zoom-format.vtt        ← Zoom sub-hour format test file
    fireflies-test.vtt     ← Fireflies export format test file
    string-cues.vtt        ← Edge case: non-numeric cue identifiers

docs/
  ingestion-architecture.md ← Full technical architecture document

PATCHES.md                 ← The two changes needed in the main repo (parse_any.py + Stage 0)
MERGE_GUIDE.md             ← Step-by-step instructions for merging these changes
WORK_PLAN.md               ← What comes next (Path B — Azure Function)
```

---

## Supported File Types

| File Type | Source | Example |
|-----------|--------|---------|
| `.vtt` | Teams, Zoom, Fireflies transcript export | Meeting recording |
| `.pdf` | Company reports, research documents | Annual report |
| `.docx` / `.doc` | Workshop outputs, written notes | Workshop summary |
| `.xlsx` / `.xlsm` | Financial models, data exports | Revenue model |
| `.pptx` / `.ppt` | Slide decks | Pitch deck |
| `.md` / `.txt` | Written notes, Notion exports | Meeting notes |

---

## Test Results — Last Run (13 July 2026)

All five tests passed with v1.2 of `parse_vtt.py`.

| Test | Format | Fragments | Result |
|------|--------|-----------|--------|
| `real-teams.vtt` | Teams multi-line cues | 6 | PASS |
| `zoom-format.vtt` | Zoom sub-hour (MM:SS) | 2 | PASS |
| `fireflies-test.vtt` | Fireflies export | 1 | PASS |
| `string-cues.vtt` | Non-numeric cue IDs | 1 | PASS |
| `AI Control Tower Catch Up.vtt` | Real meeting (Teams) | 6 | PASS |

**v1.2 fix (13 July):** Multi-line cue content in Teams exports left a stray `</v>` tag on continuation lines. Fixed with a one-line regex strip in the else branch of the cue normaliser.

---

## How to Run a Quick Test

From a terminal, with Python 3.10+ installed:

```bash
# Test the VTT parser on any transcript
python scripts/parsers/parse_vtt.py tests/fixtures/real-teams.vtt

# Expected: JSON array printed to screen, each item showing speaker + content
# Expected: NO </v> tags in the output
# Expected: At least 1 fragment returned

# Test the full auto-ingest wrapper
mkdir test-run\Evidence
copy tests\fixtures\real-teams.vtt test-run\Evidence\
python scripts/_auto_ingest.py .\test-run --client-slug test

# Expected: Meeting-Notes/ folder created inside test-run/
# Expected: real-teams_parsed.md inside Meeting-Notes/
```

---

## Environment Variables Required

These secrets must be set before running the full pipeline (not needed for parser-only tests above):

| Variable | Purpose |
|----------|---------|
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Table Storage + Blob access |
| `NOTION_COMPANY_DB_ID` | Notion company database ID |
| `NOTION_NOTES_DB_ID` | Notion meeting notes database ID |
| `NOTION_PEOPLE_DB_ID` | Notion people/contacts database ID |

**Secrets are never committed to this repo.** Load from a `.env` file at the project root.

---

## Current State (13 July 2026)

| Component | Status |
|-----------|--------|
| Path A — local file ingestion | Live and stable |
| Azure Table Storage | Live — 1,791 opportunities |
| Notion sync | Live |
| SQLite local DB | Live |
| Smoke tests Groups 1–4 | All passing |

**Next phase:** Path B — Azure Function trigger (see `WORK_PLAN.md`).

---

## Key Decisions (Already Made — No Need to Revisit)

**Why plain Python scripts, not an AI model, for file parsing?**  
Parsing is deterministic. The same PDF always produces the same fragments. This is what FCA compliance requires — you need to be able to prove that opportunity X came from page Y of document Z. AI extraction would introduce variability that breaks that chain. Cost: Python parsing is free. Claude API calls for 100 PDF pages would be ~£2 per run.

**Why three paths (local → Azure → search) instead of going straight to Azure?**  
Path A ships immediately with no infrastructure risk. Path B adds cloud capability without changing anything Path A produces. Path C adds search without changing A or B. Each is additive. The AI agents never know which path is active. Starting with Azure would have blocked the VMO2 first run by weeks.

---

*Inference Group Internal · v1.2 · 13 July 2026 · FCA-regulated — handle with care*
