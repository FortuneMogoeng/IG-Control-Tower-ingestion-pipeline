"""
core.py — pure ingestion logic for the Path B document-parser Function.

Kept free of the azure-functions SDK and of any network I/O so it can be unit
tested directly (see tests/smoke/). function_app.py is a thin Event Grid + Blob
I/O shell around these helpers.

Parser resolution works in two contexts:
  - Deployed: parsers/ is vendored next to this file.
  - Dev / tests: falls back to ../../scripts/parsers (the source of truth).
"""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

CONN_STR_ENV = "AZURE_STORAGE_CONNECTION_STRING"


def _resolve_parsers_dir() -> Path:
    """Vendored parsers/ at deploy time; scripts/parsers in dev/tests."""
    vendored = Path(__file__).parent / "parsers"
    if (vendored / "parse_any.py").exists():
        return vendored
    dev = Path(__file__).resolve().parents[2] / "scripts" / "parsers"
    if (dev / "parse_any.py").exists():
        return dev
    raise ImportError(
        "Cannot locate parsers dir. Vendor scripts/parsers into "
        "azure/document-parser-fn/parsers at deploy time."
    )


_PARSERS_DIR = _resolve_parsers_dir()
if str(_PARSERS_DIR) not in sys.path:
    sys.path.insert(0, str(_PARSERS_DIR))

from parse_any import PARSERS  # noqa: E402

# Extension allowlist. PARSERS covers binary types; add the plain-text types.
ALLOWED_EXTENSIONS = set(PARSERS.keys()) | {".md", ".txt"}


def slug_from_container(container: str) -> str:
    """intake-downing-llp -> downing-llp. Empty string if not an intake container."""
    prefix = "intake-"
    return container[len(prefix):] if container.startswith(prefix) else ""


def container_blob_from_url(blob_url: str):
    """
    Extract (container, blob_name) from a Storage blob URL.
    Returns None if the path does not contain both.
    """
    path_parts = unquote(urlparse(blob_url).path).lstrip("/").split("/", 1)
    if len(path_parts) != 2 or not path_parts[1]:
        return None
    return path_parts[0], path_parts[1]


def output_blob_name(blob_name: str) -> str:
    """kickoff.vtt -> evidence/kickoff_fragments.jsonl (consumed by _auto_ingest)."""
    return f"evidence/{Path(blob_name).stem}_fragments.jsonl"


def fragments_to_jsonl(fragments: list) -> bytes:
    """Serialise fragments to JSONL bytes (one JSON object per line)."""
    return "\n".join(json.dumps(fr) for fr in fragments).encode("utf-8")


def _frag_id_plain(path: Path, offset: int) -> str:
    """sha256 fragment id — mirrors _auto_ingest._frag_id_plain for Path A/B parity."""
    key = f"{path.name}:{offset}:{path.stat().st_size}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def parse_plain_text(path: Path) -> list:
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
    fragments: list = []

    if source_type == "md":
        current_heading = "Preamble"
        current_lines: list = []

        def _flush(heading: str, lines: list, offset: int) -> None:
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


def parse_file(local_path: Path) -> list:
    """Route a file to the correct parser. Returns fragment dicts (may be empty)."""
    ext = local_path.suffix.lower()

    if ext in (".md", ".txt"):
        return parse_plain_text(local_path)

    if ext not in PARSERS:
        return []

    mod_name = PARSERS[ext][0]
    spec = importlib.util.spec_from_file_location(mod_name, _PARSERS_DIR / f"{mod_name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parse(str(local_path))
