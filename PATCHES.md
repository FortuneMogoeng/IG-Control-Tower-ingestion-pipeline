# Deployment Patches — Ingestion Pipeline v1.2 (13 July 2026)

Two patches apply to existing files in the main `ig-plugins` repo.  
The three new/updated files (`parse_vtt.py`, `parse_any.py`, `_auto_ingest.py`) are copy-in replacements — see `MERGE_GUIDE.md`.

---

## PATCH 1 — `parse_any.py` (one line, already applied in `scripts/parsers/`)

The `.vtt` extension has been added to the `PARSERS` dispatch dictionary.

If you prefer to apply it manually rather than copying the whole file, open the existing `parse_any.py` and add this line to the `PARSERS` dict:

```python
".vtt":  ("parse_vtt",   "stdlib"),     # ← ADD THIS LINE
```

The full dict after the patch:

```python
PARSERS = {
    ".pdf":  ("parse_pdf",   "pdfplumber"),
    ".docx": ("parse_word",  "python-docx"),
    ".doc":  ("parse_word",  "python-docx"),
    ".xlsx": ("parse_excel", "openpyxl"),
    ".xlsm": ("parse_excel", "openpyxl"),
    ".pptx": ("parse_pptx",  "python-pptx"),
    ".ppt":  ("parse_pptx",  "python-pptx"),
    ".vtt":  ("parse_vtt",   "stdlib"),     # ← ADDED 09-Jul-2026
}
```

---

## PATCH 2 — `SKILL.md` Stage 0 (12 lines)

Find the Stage 0 block in `ig-AI-opportunity-discovery/SKILL.md`.  
Add this block **after** the `init_project.py` / scaffold call, **before** any agent calls:

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

> `project_root` and `company_slug` must match the variable names already used in Stage 0.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.2 | 13 July 2026 | `parse_vtt.py`: fixed `</v>` tags on multi-line Teams cue continuation lines |
| v1.1 | 09 July 2026 | 7 parse_vtt fixes + 9 _auto_ingest fixes + Stage 0 returncode guard |
| v1.0 | 08 July 2026 | Initial deployment: parse_vtt.py created, _auto_ingest.py created, parse_any.py patched |

---

*Inference Group Internal · 13 July 2026*
