"""
Group 7 — Full E2E and schema/parity checks.

Most of these run offline (no Azure). They validate that the consolidated repo
ingests end to end, that the frozen fragment schema holds, and that Path A and
Path B produce identical fragments for the same input.
"""

import json
import re
import sqlite3
from pathlib import Path

import pytest

import _auto_ingest
import core
import parse_vtt

CANONICAL_KEYS = {
    "fragment_id", "source_file", "source_type", "client_slug",
    "content", "metadata", "char_count", "ingested_at",
}
METADATA_KEYS = {"timestamp", "speaker", "page", "slide", "sheet", "section"}
_HEX16 = re.compile(r"^[0-9a-f]{16}$")

SAMPLE_MD = (
    "# Kickoff\n\n"
    "This body is comfortably longer than the thirty character minimum.\n\n"
    "# Risks\n\n"
    "Data residency and FCA traceability were discussed at length today.\n"
)


def _assert_canonical(frag: dict) -> None:
    assert CANONICAL_KEYS <= set(frag), f"missing keys: {CANONICAL_KEYS - set(frag)}"
    assert _HEX16.match(frag["fragment_id"]), f"bad id: {frag['fragment_id']}"
    assert isinstance(frag["content"], str) and frag["content"].strip()
    assert METADATA_KEYS <= set(frag["metadata"])


def test_path_a_end_to_end(tmp_path, fixtures_dir):
    """Evidence/ with a VTT and a Markdown file ingests with zero errors."""
    evidence = tmp_path / "Evidence"
    evidence.mkdir()
    (evidence / "call.vtt").write_bytes((fixtures_dir / "real-teams.vtt").read_bytes())
    (evidence / "notes.md").write_text(SAMPLE_MD, encoding="utf-8")

    result = _auto_ingest.ingest(str(tmp_path), client_slug="smoke")

    assert result["errors"] == []
    assert result["ingested"] == 2
    notes = list((tmp_path / "Meeting-Notes").glob("*_parsed.md"))
    assert len(notes) == 2


def test_vtt_fragments_are_canonical(fixtures_dir):
    frags = parse_vtt.parse(str(fixtures_dir / "real-teams.vtt"))
    assert frags, "expected fragments from real-teams.vtt"
    for fr in frags:
        _assert_canonical(fr)


def test_plain_text_fragments_are_canonical(tmp_path):
    md = tmp_path / "notes.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    frags = core.parse_plain_text(md)
    assert len(frags) == 2
    for fr in frags:
        _assert_canonical(fr)


def test_path_a_b_plain_text_parity(tmp_path):
    """Path B (core) and Path A (_auto_ingest) emit byte-identical md fragments."""
    md = tmp_path / "notes.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    a = _auto_ingest._parse_plain_text(md)
    b = core.parse_plain_text(md)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_fragment_id_stable_across_reparse(fixtures_dir):
    """sha256 ids must be deterministic across runs (FCA lineage requirement)."""
    f = str(fixtures_dir / "real-teams.vtt")
    ids1 = [x["fragment_id"] for x in parse_vtt.parse(f)]
    ids2 = [x["fragment_id"] for x in parse_vtt.parse(f)]
    assert ids1 == ids2 and len(ids1) == len(set(ids1))


def test_sqlite_opportunity_count():
    """Local SQLite carries the seed corpus (>= 1,791 generic opportunities)."""
    db = Path.home() / ".claude" / "data" / "ig-control-tower.db"
    if not db.exists():
        pytest.skip(f"DB not present at {db}")
    con = sqlite3.connect(str(db))
    try:
        n = con.execute("SELECT COUNT(*) FROM generic_opportunities").fetchone()[0]
    finally:
        con.close()
    assert n >= 1791
