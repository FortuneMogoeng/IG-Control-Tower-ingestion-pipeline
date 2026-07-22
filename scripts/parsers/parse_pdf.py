"""
parse_pdf.py — PDF parser for AI Control Tower ingestion pipeline.
Extracts text page-by-page using pdfplumber and emits provenance-tagged
fragments to stdout as JSON Lines (one JSON object per page).

Usage:
    python parse_pdf.py <path/to/file.pdf>

Output (stdout, one JSON object per line):
    {
        "fragment_id": "uuid4",
        "source_file": "filename.pdf",
        "file_type": "pdf",
        "location": "page 3",
        "text": "...",
        "char_count": 412
    }

Requires: pdfplumber  (pip install pdfplumber)
"""

import json
import sys
import uuid
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber not installed. Run: pip install pdfplumber")


MIN_CHARS = 30  # skip pages that are essentially blank


def parse(path: str) -> list[dict]:
    source = Path(path)
    fragments = []

    with pdfplumber.open(source) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()

            if len(text) < MIN_CHARS:
                continue  # skip blank/header-only pages

            fragments.append({
                "fragment_id": str(uuid.uuid4()),
                "source_file": source.name,
                "file_type": "pdf",
                "location": f"page {page_num}",
                "text": text,
                "char_count": len(text),
            })

    return fragments


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python parse_pdf.py <file.pdf>")

    for fragment in parse(sys.argv[1]):
        print(json.dumps(fragment))


if __name__ == "__main__":
    main()
