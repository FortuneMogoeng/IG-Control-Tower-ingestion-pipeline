"""
document-parser-fn — Path B Azure Function for IG Control Tower ingestion.

Triggers on a BlobCreated event (via Event Grid) when a consultant uploads a
client file to `intake-{client-slug}/` in Azure Blob Storage. Runs the existing
deterministic parser for that file type and writes the fragments as JSONL to
`processed-{client-slug}/evidence/{stem}_fragments.jsonl`.

The pipeline consumer `_auto_ingest._download_azure_fragments()` then pulls those
JSONL files into Meeting-Notes/ on the next run. No consultant needs the pipeline
running on their own laptop.

Design notes (locked decisions — see CLAUDE_HANDOVER.md):
  - Parsing is deterministic Python only. This Function never calls Claude.
  - It reuses parse_any.PARSERS unchanged — no new parsing code.
  - fragment_id stays sha256-based (set by the parsers, not here).
  - Extension allowlist is enforced; anything else is ignored (logged).

Deploy: see README.md in this folder. `parsers/` must be vendored alongside this
file at deploy time (the deploy step copies ../../scripts/parsers here).
"""

import hashlib
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse, unquote

import azure.functions as func

# ---------------------------------------------------------------------------
# Parser wiring — parsers/ is vendored next to this file at deploy time.
# ---------------------------------------------------------------------------
_PARSERS_DIR = Path(__file__).parent / "parsers"
if str(_PARSERS_DIR) not in sys.path:
    sys.path.insert(0, str(_PARSERS_DIR))

from parse_any import PARSERS  # noqa: E402

# Extension allowlist (WORK_PLAN.md). PARSERS covers the binary types; add the
# plain-text types the pipeline also accepts.
ALLOWED_EXTENSIONS = set(PARSERS.keys()) | {".md", ".txt"}

CONN_STR_ENV = "AZURE_STORAGE_CONNECTION_STRING"

app = func.FunctionApp()


def _slug_from_container(container: str) -> str:
    """intake-downing-llp -> downing-llp. Empty string if not an intake container."""
    prefix = "intake-"
    return container[len(prefix):] if container.startswith(prefix) else ""


def _frag_id_plain(path: Path, offset: int) -> str:
    """sha256 fragment id — mirrors _auto_ingest._frag_id_plain for Path A/B parity."""
    key = f"{path.name}:{offset}:{path.stat().st_size}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _parse_plain_text(path: Path) -> list[dict]:
    """
    Canonical .md/.txt parser — kept byte-for-byte consistent with
    _auto_ingest._parse_plain_text so Path B produces identical fragments to
    Path A (sha256 ids, content/metadata schema). Do NOT swap for
    parse_any.parse_md_txt, which uses the older uuid4 6-field schema.
    """
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []

    source_type = "md" if path.suffix.lower() == ".md" else "txt"
    fragments: list[dict] = []

    if source_type == "md":
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

        for line in text.splitlines():
            if line.startswith("# "):
                _flush(current_heading, current_lines, len(fragments))
                current_heading = line.lstrip("# ").strip()
                current_lines = []
            else:
                current_lines.append(line)
        _flush(current_heading, current_lines, len(fragments))
    else:
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


def _parse_file(local_path: Path) -> list[dict]:
    """Route a downloaded file to the correct parser. Returns fragment dicts."""
    ext = local_path.suffix.lower()

    if ext in (".md", ".txt"):
        return _parse_plain_text(local_path)

    if ext not in PARSERS:
        return []

    mod_name = PARSERS[ext][0]
    import importlib.util  # noqa: PLC0415
    spec = importlib.util.spec_from_file_location(mod_name, _PARSERS_DIR / f"{mod_name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parse(str(local_path))


@app.function_name(name="documentParser")
@app.event_grid_trigger(arg_name="event")
def document_parser(event: func.EventGridEvent) -> None:
    """
    Handle a Storage BlobCreated event.

    Event subject looks like:
      /blobServices/default/containers/intake-downing-llp/blobs/kickoff.vtt
    """
    data = event.get_json()
    blob_url = data.get("url", "")
    logging.info("BlobCreated event for: %s", blob_url)

    # Parse container + blob name out of the URL path.
    path_parts = unquote(urlparse(blob_url).path).lstrip("/").split("/", 1)
    if len(path_parts) != 2:
        logging.warning("Cannot parse container/blob from url: %s", blob_url)
        return
    container, blob_name = path_parts

    client_slug = _slug_from_container(container)
    if not client_slug:
        logging.info("Container %s is not an intake-* container; ignoring.", container)
        return

    ext = Path(blob_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        logging.info("Extension %s not in allowlist; ignoring %s.", ext, blob_name)
        return

    conn_str = os.environ.get(CONN_STR_ENV)
    if not conn_str:
        logging.error("%s not configured; cannot process blob.", CONN_STR_ENV)
        return

    from azure.storage.blob import BlobServiceClient  # noqa: PLC0415
    svc = BlobServiceClient.from_connection_string(conn_str)

    # 1. Download the uploaded blob to a temp file (parsers need a real path).
    src = svc.get_blob_client(container=container, blob=blob_name)
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / Path(blob_name).name
        local.write_bytes(src.download_blob().readall())

        # 2. Parse deterministically.
        try:
            fragments = _parse_file(local)
        except Exception:
            logging.exception("Parsing failed for %s", blob_name)
            return

        if not fragments:
            logging.warning("No fragments extracted from %s", blob_name)
            return

        # Backfill client_slug so downstream lineage is complete.
        for fr in fragments:
            fr["client_slug"] = client_slug

    # 3. Write fragments as JSONL to processed-{slug}/evidence/{stem}_fragments.jsonl
    stem = Path(blob_name).stem
    out_name = f"evidence/{stem}_fragments.jsonl"
    payload = "\n".join(json.dumps(fr) for fr in fragments).encode("utf-8")

    dst_container = f"processed-{client_slug}"
    dst = svc.get_blob_client(container=dst_container, blob=out_name)
    dst.upload_blob(payload, overwrite=True)

    logging.info(
        "Wrote %d fragment(s) to %s/%s", len(fragments), dst_container, out_name
    )
