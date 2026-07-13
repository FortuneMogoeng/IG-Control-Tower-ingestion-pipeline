# Merge Guide — Ingestion Pipeline v1.2

**For:** The person with write access to the main `ig-plugins` branch  
**Time required:** ~30 minutes  
**Risk:** Low — these are additive changes only. No existing files are removed. No existing behaviour changes.

---

## What You Are Merging

Three new/updated files + one edit to an existing file in the `ig-plugins` repo:

| This repo | Goes to (in `ig-plugins`) | Action |
|-----------|--------------------------|--------|
| `scripts/parsers/parse_vtt.py` | `plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/parsers/parse_vtt.py` | **Copy in — new file** |
| `scripts/parsers/parse_any.py` | `plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/parsers/parse_any.py` | **Replace — one line added** |
| `scripts/_auto_ingest.py` | `plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/_auto_ingest.py` | **Copy in — new file** |
| See `PATCHES.md` → Patch 2 | `plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/SKILL.md` Stage 0 block | **Edit — 12 lines added** |

---

## Step-by-Step Instructions

### Step 1 — Create a branch in `ig-plugins`

In your local clone of the `ig-plugins` repo, create a feature branch:

```bash
git checkout main
git pull origin main
git checkout -b feature/ingestion-pipeline-v1.2
```

### Step 2 — Copy `parse_vtt.py` (new file)

Copy `scripts/parsers/parse_vtt.py` from this repo to:

```
{ig-plugins}/plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/parsers/parse_vtt.py
```

This file did not previously exist. It is the WebVTT transcript parser for Teams, Zoom, and Fireflies recordings.

### Step 3 — Replace `parse_any.py` (one line added)

Copy `scripts/parsers/parse_any.py` from this repo over the existing file at:

```
{ig-plugins}/plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/parsers/parse_any.py
```

**What changed:** One line added to the `PARSERS` dictionary:
```python
".vtt":  ("parse_vtt",   "stdlib"),     # ← ADDED 09-Jul-2026
```

If you prefer to apply it manually rather than replacing the whole file, open `parse_any.py` and add that line to the `PARSERS` dict.

### Step 4 — Copy `_auto_ingest.py` (new file)

Copy `scripts/_auto_ingest.py` from this repo to:

```
{ig-plugins}/plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/_auto_ingest.py
```

This file did not previously exist. It is the Stage 0 wrapper that scans `Evidence/` and runs all parsers automatically.

### Step 5 — Edit `SKILL.md` Stage 0 block (12 lines)

Open `SKILL.md` in the `ig-AI-opportunity-discovery` skill. Find the Stage 0 section — specifically the block that calls `init_project.py` and scaffolds the folder structure.

Add the following block **after** the scaffold / `init_project.py` call, **before** any agent calls begin:

```python
import subprocess, sys, json

_ingest = subprocess.run(
    [sys.executable, "scripts/_auto_ingest.py", project_root,
     "--client-slug", company_slug],
    capture_output=True, text=True
)
if _ingest.returncode != 0:
    print(f"  ⚠ Auto-ingest exited with code {_ingest.returncode}. "
          f"Check Evidence/ folder. stderr: {_ingest.stderr[:200]}")
elif _ingest.stdout.strip():
    _r = json.loads(_ingest.stdout)
    print(f"  Auto-ingested: {_r['ingested']} file(s), "
          f"{_r['skipped']} skipped, {len(_r['errors'])} error(s)")
    if _r["errors"]:
        for e in _r["errors"]:
            print(f"    ✗ {e['file']}: {e['error']}")
```

> **Variable names:** `project_root` and `company_slug` must match the variable names already used in Stage 0. If Stage 0 uses different names (e.g. `engagement_dir`, `client_name`) — substitute accordingly. The values are the project folder path and the client identifier string.

### Step 6 — Verify the file structure

After all copies, confirm this structure exists in `ig-plugins`:

```
plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/
├── parsers/
│   ├── parse_any.py       ← updated (1 line added)
│   ├── parse_pdf.py       ← unchanged
│   ├── parse_word.py      ← unchanged
│   ├── parse_excel.py     ← unchanged
│   ├── parse_pptx.py      ← unchanged
│   └── parse_vtt.py       ← NEW
└── _auto_ingest.py        ← NEW
```

### Step 7 — Run the smoke tests

From the ig-plugins repo root, run the quick smoke test:

```bash
# Test parse_vtt standalone (Teams format)
python plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/parsers/parse_vtt.py \
  "path/to/any-teams-call.vtt"

# Expected: JSON array with speaker-labelled content, no </v> tags, at least 1 fragment

# Test auto-ingest wrapper
mkdir test-run\Evidence
copy "path/to/any-teams-call.vtt" test-run\Evidence\
python plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/_auto_ingest.py \
  .\test-run --client-slug test-client

# Expected: Meeting-Notes/ folder created with one *_parsed.md file
```

Use the VTT fixture files from `tests/fixtures/` in this repo if you do not have a client transcript handy.

### Step 8 — Commit and PR

```bash
git add plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/parsers/parse_vtt.py
git add plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/parsers/parse_any.py
git add plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/scripts/_auto_ingest.py
git add plugins/ig-control-tower/skills/ig-AI-opportunity-discovery/SKILL.md

git commit -m "feat(ingestion): add Path A auto-ingest — parse_vtt v1.2, _auto_ingest v1.1, parse_any .vtt dispatch

- parse_vtt.py: WebVTT parser for Teams/Zoom/Fireflies, 2-min speaker windows,
  stable fragment IDs (sha256 of filename+window_ts), stdlib only
- _auto_ingest.py: Stage 0 wrapper, scans Evidence/, dispatches all parsers,
  writes Meeting-Notes/*.md, backward-compatible with Path B Azure mode
- parse_any.py: .vtt added to PARSERS dispatch dict
- SKILL.md Stage 0: calls _auto_ingest.py before agents run, guards returncode

Fixes: </v> tags in multi-line Teams cues (v1.2), KeyError for old parsers,
page-0 falsy trap, MD heading splitting, fragment ID collision across clients.
Tests: 5/5 fixture + real-meeting PASS on 13 July 2026."

git push origin feature/ingestion-pipeline-v1.2
```

Then open a pull request against `main`.

---

## What Not to Change

- All 19 skills — do not touch
- All 40+ agent prompts — do not touch
- All 8 discovery stages (1–5, A–G) — do not touch
- Notion integration — do not touch
- `_progress.json` / `_todo.json` resumability — do not touch
- The fragment schema (13 fields) — do not add or remove required fields without updating all parsers

---

## If Something Goes Wrong

**"ModuleNotFoundError: No module named 'parse_vtt'"**  
→ `parse_vtt.py` is not in the `parsers/` directory, or `parse_any.py` was not saved after the edit. Re-check Steps 2 and 3.

**"JSONDecodeError" in Stage 0**  
→ Run `_auto_ingest.py` standalone first (Step 7) to see the actual error.

**"UnicodeEncodeError" on Windows**  
→ Run `set PYTHONIOENCODING=utf-8` before running the script.

---

*Inference Group Internal · 13 July 2026*
