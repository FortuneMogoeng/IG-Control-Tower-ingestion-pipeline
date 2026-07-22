"""
parse_word.py — Word (.docx) parser for AI Control Tower ingestion pipeline.
Splits the document by heading boundaries into logical sections and emits
provenance-tagged fragments as JSON Lines (one per section).

Usage:
    python parse_word.py <path/to/file.docx>

Output (stdout, one JSON object per line):
    {
        "fragment_id": "uuid4",
        "source_file": "filename.docx",
        "file_type": "docx",
        "location": "Section: 'Executive Summary' (paragraph 5)",
        "text": "...",
        "char_count": 634
    }

Requires: python-docx  (pip install python-docx)
"""

import json
import sys
import uuid
from pathlib import Path

try:
    from docx import Document
    from docx.oxml.ns import qn
except ImportError:
    sys.exit("python-docx not installed. Run: pip install python-docx")


MIN_CHARS = 40
MAX_SECTION_CHARS = 3000  # split oversized sections at paragraph boundaries


def is_heading(para) -> bool:
    return para.style.name.startswith("Heading")


def flush_section(fragments: list, source_name: str, section_title: str,
                  start_para: int, paragraphs: list[str]) -> None:
    text = "\n".join(p for p in paragraphs if p.strip())
    if len(text) < MIN_CHARS:
        return

    # Split oversized sections into chunks of MAX_SECTION_CHARS
    chunks = []
    current = []
    current_len = 0
    for para in paragraphs:
        if current_len + len(para) > MAX_SECTION_CHARS and current:
            chunks.append("\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += len(para)
    if current:
        chunks.append("\n".join(current))

    for chunk_i, chunk_text in enumerate(chunks):
        chunk_text = chunk_text.strip()
        if len(chunk_text) < MIN_CHARS:
            continue
        location = f"Section: '{section_title}' (para {start_para})"
        if len(chunks) > 1:
            location += f" part {chunk_i + 1}/{len(chunks)}"
        fragments.append({
            "fragment_id": str(uuid.uuid4()),
            "source_file": source_name,
            "file_type": "docx",
            "location": location,
            "text": chunk_text,
            "char_count": len(chunk_text),
        })


def parse(path: str) -> list[dict]:
    source = Path(path)
    doc = Document(source)
    fragments: list[dict] = []

    current_title = "Preamble"
    current_start = 1
    current_paras: list[str] = []

    for para_i, para in enumerate(doc.paragraphs, start=1):
        text = para.text.strip()
        if not text:
            continue

        if is_heading(para):
            # Flush accumulated paragraphs before starting new section
            flush_section(fragments, source.name, current_title,
                          current_start, current_paras)
            current_title = text
            current_start = para_i
            current_paras = []
        else:
            current_paras.append(text)

    # Flush final section
    flush_section(fragments, source.name, current_title,
                  current_start, current_paras)

    return fragments


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python parse_word.py <file.docx>")

    for fragment in parse(sys.argv[1]):
        print(json.dumps(fragment))


if __name__ == "__main__":
    main()
