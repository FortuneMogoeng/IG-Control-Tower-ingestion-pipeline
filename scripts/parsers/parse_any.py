"""
parse_any.py — Dispatcher for AI Control Tower ingestion pipeline.
Routes a file to the correct parser based on extension and writes all
fragments to <engagement_dir>/evidence/fragments.jsonl (appending).

Usage:
    python parse_any.py <file_path> [--engagement-dir <dir>]

    --engagement-dir defaults to ./evidence relative to the file's parent.

The fragment schema written per line:
    {
        "fragment_id": "uuid4",
        "source_file": "filename.ext",
        "file_type":   "pdf | docx | xlsx | pptx | md | txt",
        "location":    "page 3 | Section: 'X' | Slide 4 | ...",
        "text":        "...",
        "char_count":  N
    }
"""

import argparse
import json
import sys
from pathlib import Path

# Import sibling parsers — works when all files are in the same directory
import importlib.util, os

_HERE = Path(__file__).parent


def _load(module_name: str):
    spec = importlib.util.spec_from_file_location(
        module_name, _HERE / f"{module_name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def parse_md_txt(path: Path) -> list[dict]:
    """Inline parser for plain text and markdown — no extra dependencies."""
    import uuid
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    # Split markdown by top-level headings; plain text treated as one block
    sections = []
    if path.suffix.lower() == ".md":
        current_heading = "Preamble"
        current_lines: list[str] = []
        for line in text.splitlines():
            if line.startswith("# "):
                if current_lines:
                    sections.append((current_heading, "\n".join(current_lines)))
                current_heading = line.lstrip("# ").strip()
                current_lines = []
            else:
                current_lines.append(line)
        if current_lines:
            sections.append((current_heading, "\n".join(current_lines)))
    else:
        sections = [("full document", text)]

    fragments = []
    for heading, body in sections:
        body = body.strip()
        if len(body) < 30:
            continue
        fragments.append({
            "fragment_id": str(uuid.uuid4()),
            "source_file": path.name,
            "file_type": path.suffix.lstrip(".").lower(),
            "location": f"Section: '{heading}'",
            "text": body,
            "char_count": len(body),
        })
    return fragments


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file_path")
    parser.add_argument("--engagement-dir", default=None,
                        help="Directory to write evidence/fragments.jsonl")
    args = parser.parse_args()

    file_path = Path(args.file_path).resolve()
    if not file_path.exists():
        sys.exit(f"File not found: {file_path}")

    ext = file_path.suffix.lower()

    # Route to correct parser
    if ext in (".md", ".txt"):
        fragments = parse_md_txt(file_path)
    elif ext in PARSERS:
        module_name, dep = PARSERS[ext]
        try:
            mod = _load(module_name)
        except Exception as e:
            sys.exit(f"Could not load {module_name}.py: {e}\n"
                     f"Make sure {dep} is installed.")
        fragments = mod.parse(str(file_path))
    else:
        sys.exit(f"Unsupported file type: {ext}. "
                 f"Supported: {' '.join(sorted(PARSERS.keys()))} .md .txt")

    if not fragments:
        print(f"[parse_any] No fragments extracted from {file_path.name}",
              file=sys.stderr)
        return

    # Determine output path
    if args.engagement_dir:
        evidence_dir = Path(args.engagement_dir) / "evidence"
    else:
        evidence_dir = file_path.parent / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    out_file = evidence_dir / "fragments.jsonl"
    with out_file.open("a", encoding="utf-8") as f:
        for frag in fragments:
            f.write(json.dumps(frag) + "\n")

    print(f"[parse_any] {file_path.name} -> {len(fragments)} fragments "
          f"appended to {out_file}")


if __name__ == "__main__":
    main()
