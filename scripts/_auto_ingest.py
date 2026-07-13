"""
_auto_ingest.py — Stage 0 ingestion wrapper for IG Control Tower.

Called by Stage 0 before any agents run.
Scans Evidence/ for all supported files, runs the correct parser,
backfills client_slug and ingested_at, and writes Meeting-Notes-compatible
.md files that Stage 1 (ig-meeting-discovery) picks up automatically.

Usage (standalone):
    python scripts/_auto_ingest.py /path/to/project --client-slug downing-llp

Usage (from Stage 0):
    See PATCHES.md for the Stage 0 addition.

Changes vs 08-July version:
  - _write_meeting_note: fr["content"] → fr.get("content") or fr.get("text", "")
    fixes KeyError for all existing parsers (pdf, word, excel, pptx)
  - _write_meeting_note: falls back to fr.get("location") when metadata absent,
    so positional context (page N, slide N) from old parsers is preserved
  - _write_meeting_note: meta.get("page") guard uses `is not None` to handle page 0
  - _parse_plain_text: .md files split by heading boundaries (not one monolithic fragment)
  - _parse_plain_text: fragment_id includes content hash for cross-client uniqueness
  - _load_parser: module-level cache avoids re-importing the same parser for every file
  - _download_azure_fragments: per-blob exception handling so one bad blob
    does not abort remaining blobs; errors returned in result dict
  - sys.path insert guarded to avoid duplicate insertions
"""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import sys
from types import ModuleType

# ---------------------------------------------------------------------------
# Path setup — guarded to avoid polluting sys.path more than once
# ---------------------------------------------------------------------------
_PARSERS_DIR = Path(__file__).parent / "parsers"
_parsers_dir_str = str(_PARSERS_DIR)
if _parsers_dir_str not in sys.path:
    sys.path.insert(0, _parsers_dir_str)

from parse_any import PARSERS  # noqa: E402

SUPPORTED_EXTENSIONS = set(PARSERS.keys()) | {".md", ".txt"}

# ---------------------------------------------------------------------------
# Parser module cache — avoids re-importing parse_pdf etc. per file
# ---------------------------------------------------------------------------
_parser_cache: dict[str, ModuleType] = {}


def _load_parser(ext: str) -> ModuleType:
    """Load (and cache) the parser module for a given file extension."""
    mod_name = PARSERS[ext][0]
    if mod_name not in _parser_cache:
        spec = importlib.util.spec_from_file_location(
            mod_name, _PARSERS_DIR / f"{mod_name}.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot find parser module: {mod_name}.py in {_PARSERS_DIR}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _parser_cache[mod_name] = mod
    return _parser_cache[mod_name]


# ---------------------------------------------------------------------------
# Plain-text / Markdown inline parser
# ---------------------------------------------------------------------------

def _frag_id_plain(path: Path, offset: int) -> str:
    key = f"{path.name}:{offset}:{path.stat().st_size}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _parse_plain_text(path: Path) -> list:
    """
    Parser for .md and .txt files.
    Markdown is split by top-level headings; plain text is one block.
    Returns fragments in the canonical new schema (content / source_type / metadata).
    """
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []

    source_type = "md" if path.suffix.lower() == ".md" else "txt"
    fragments = []

    if source_type == "md":
        # Split at top-level headings (# Heading)
        current_heading = "Preamble"
        current_lines: list[str] = []

        def _flush(heading: str, lines: list[str], offset: int) -> None:
            body = "\n".join(lines).strip()
            if len(body) < 30:
                return
            fragments.append({
                "fragment_id": _frag_id_plain(path, offset),
                "source_file": path.name,
                "source_type": source_type,
                "client_slug": "",
                "content": body,
                "metadata": {
                    "timestamp": None, "speaker": None, "page": None,
                    "slide": None, "sheet": None, "section": heading,
                },
                "char_count": len(body),
                "ingested_at": "",
            })

        for i, line in enumerate(text.splitlines()):
            if line.startswith("# "):
                _flush(current_heading, current_lines, len(fragments))
                current_heading = line.lstrip("# ").strip()
                current_lines = []
            else:
                current_lines.append(line)
        _flush(current_heading, current_lines, len(fragments))

    else:
        # Plain text: one fragment
        fragments.append({
            "fragment_id": _frag_id_plain(path, 0),
            "source_file": path.name,
            "source_type": source_type,
            "client_slug": "",
            "content": text,
            "metadata": {
                "timestamp": None, "speaker": None, "page": None,
                "slide": None, "sheet": None, "section": None,
            },
            "char_count": len(text),
            "ingested_at": "",
        })

    return fragments


# ---------------------------------------------------------------------------
# Meeting-Notes writer — handles both old and new fragment schemas
# ---------------------------------------------------------------------------

def _write_meeting_note(out_path: Path, source_name: str, frags: list) -> None:
    """
    Write fragments as a Meeting-Notes-compatible markdown file.

    Accepts both the new canonical schema (content / metadata) and the old
    schema (text / location / file_type) so all existing parsers work without
    modification.
    """
    parts = [f"# {source_name} (auto-ingested)\n"]

    for fr in frags:
        # ── content field ──────────────────────────────────────────────────
        # New schema: "content"; old parsers (pdf/word/excel/pptx): "text"
        body = fr.get("content") or fr.get("text", "")

        # ── location label ─────────────────────────────────────────────────
        meta = fr.get("metadata") or {}
        ts = meta.get("timestamp")
        page = meta.get("page")       # may be 0 — use `is not None`
        slide = meta.get("slide")     # same
        sheet = meta.get("sheet")
        section = meta.get("section")

        loc = (
            ts
            or (f"p.{page}" if page is not None else None)
            or (f"slide {slide}" if slide is not None else None)
            or sheet
            or section
            # fallback for old-schema parsers that carry a flat "location" string
            or fr.get("location", "")
        )

        header = f"**[{loc}]**" if loc else ""
        parts.append((header + "\n\n" if header else "") + body)

    out_path.write_text("\n\n---\n\n".join(parts), encoding="utf-8")


# ---------------------------------------------------------------------------
# Azure Blob downloader (Path B)
# ---------------------------------------------------------------------------

def _download_azure_fragments(client_slug: str, notes_dir: Path) -> tuple[int, list]:
    """
    Pull processed fragments from Azure Blob processed-{client_slug}/evidence/.

    Silently no-ops when AZURE_STORAGE_CONNECTION_STRING is not set (Path A).
    Returns (count_of_files_written, list_of_error_dicts).
    """
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        return 0, []

    try:
        from azure.storage.blob import BlobServiceClient  # noqa: PLC0415
    except ImportError:
        return 0, []

    count = 0
    errors: list[dict] = []

    try:
        svc = BlobServiceClient.from_connection_string(conn_str)
        container = f"processed-{client_slug}"
        cc = svc.get_container_client(container)
        blobs = list(cc.list_blobs(name_starts_with="evidence/"))
    except Exception as exc:
        print(f"  Azure Blob listing skipped: {exc}", file=sys.stderr)
        return 0, []

    for blob in blobs:
        try:
            raw = cc.get_blob_client(blob.name).download_blob().readall()
            frags = [
                json.loads(line)
                for line in raw.decode("utf-8").splitlines()
                if line.strip()
            ]
            stem = Path(blob.name).stem.replace("_fragments", "")
            out = notes_dir / f"{stem}_azure_parsed.md"
            _write_meeting_note(out, stem, frags)
            count += 1
        except Exception as exc:
            errors.append({"file": blob.name, "error": str(exc)})
            print(f"  ✗ Azure blob {blob.name}: {exc}", file=sys.stderr)

    return count, errors


# ---------------------------------------------------------------------------
# Main ingestion entry point
# ---------------------------------------------------------------------------

def ingest(project_root: str, client_slug: str = "") -> dict:
    """
    Scan Evidence/ and ingest all supported files.

    Returns:
        dict with keys: ingested (int), skipped (int), errors (list of dicts)
    """
    root = Path(project_root)
    evidence_dir = root / "Evidence"
    notes_dir = root / "Meeting-Notes"

    if not evidence_dir.exists():
        print(f"  No Evidence/ folder found at {evidence_dir} — skipping", file=sys.stderr)
        return {"ingested": 0, "skipped": 0, "errors": []}

    notes_dir.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    ingested = 0
    skipped = 0
    errors: list[dict] = []

    for file_path in sorted(evidence_dir.iterdir()):
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            skipped += 1
            print(f"  — {file_path.name} (unsupported: {ext})", file=sys.stderr)
            continue

        try:
            if ext in (".md", ".txt"):
                frags = _parse_plain_text(file_path)
            else:
                mod = _load_parser(ext)
                frags = mod.parse(str(file_path))

            # Backfill fields that parsers leave blank
            for fr in frags:
                fr["client_slug"] = client_slug
                fr["ingested_at"] = now

            out = notes_dir / f"{file_path.stem}_parsed.md"
            _write_meeting_note(out, file_path.name, frags)

            ingested += 1
            print(
                f"  ✓ {file_path.name} → {len(frags)} fragment(s) → {out.name}",
                file=sys.stderr,
            )

        except Exception as exc:
            errors.append({"file": file_path.name, "error": str(exc)})
            print(f"  ✗ {file_path.name}: {exc}", file=sys.stderr)

    # Path B: pull Azure Blob fragments if connection string is set
    azure_count, azure_errors = _download_azure_fragments(client_slug, notes_dir)
    if azure_count:
        print(f"  ✓ {azure_count} fragment file(s) pulled from Azure Blob", file=sys.stderr)
    errors.extend(azure_errors)

    return {"ingested": ingested + azure_count, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(
        description="Auto-ingest Evidence/ files for IG Control Tower"
    )
    ap.add_argument("project_root", help="Path to the engagement project folder")
    ap.add_argument(
        "--client-slug",
        default="",
        help="e.g. downing-llp or vmo2 (used for Azure Blob container name)",
    )
    args = ap.parse_args()

    result = ingest(args.project_root, args.client_slug)
    print(json.dumps(result, indent=2))
