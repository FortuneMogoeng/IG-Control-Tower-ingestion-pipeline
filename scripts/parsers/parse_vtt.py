"""
parse_vtt.py — WebVTT transcript parser for IG Control Tower ingestion layer.

Handles .vtt files from Teams, Zoom, and Fireflies.
Groups speaker turns into 2-minute windows to preserve conversational context.

Output: list of fragment dicts matching the canonical fragment schema.
client_slug and ingested_at are backfilled by _auto_ingest.py.

Changes vs 08-July version (v1.2 — 13 July 2026):
  - Multi-line cue continuation lines now have trailing </v> stripped
    (Teams exports can span a cue over multiple lines; only the opening
    line matched _SP_RE, so </v> appeared in fragment content — fixed)

Changes vs 08-July version (v1.1 — 09 July 2026):
  - _TS_RE now accepts Zoom short format MM:SS.mmm (was HH:MM:SS only)
  - _SP_RE strips closing </v> tag (Teams exports use <v X>text</v>)
  - NOTE block lines no longer bleed into transcript content
  - Non-numeric cue identifiers no longer appended as spoken lines
  - fragment_id uses window timestamp for stability across re-ingestion
  - char_count computed from stored content string (no double join)
  - _ts_to_seconds handles both 2-part and 3-part timestamp formats
"""

import re
from pathlib import Path
import hashlib

# Matches HH:MM:SS.mmm or short MM:SS.mmm (Zoom sub-hour calls)
_TS_RE = re.compile(r"(\d{1,2}:\d{2}(?::\d{2})?)\.\d+ -->")

# Captures speaker and content; optional </v> closing tag is stripped
_SP_RE = re.compile(r"^<v ([^>]+)>(.+?)(?:</v>)?\s*$")

WINDOW_SECONDS = 120  # 2-minute grouping window


def _frag_id(source: str, window_ts: str) -> str:
    """Deterministic ID based on source filename and window start timestamp."""
    return hashlib.sha256(f"{source}{window_ts}".encode()).hexdigest()[:16]


def _ts_to_seconds(ts: str) -> int:
    """Convert HH:MM:SS or MM:SS to total seconds."""
    parts = list(map(int, ts.split(":")))
    if len(parts) == 2:          # MM:SS (Zoom short format)
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]  # HH:MM:SS


def parse(path: str) -> list:
    """Parse a .vtt file and return a list of fragment dicts."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")

    # Step 1: collect raw (timestamp, lines) pairs
    raw_blocks = []
    current_ts = "00:00:00"
    current_lines: list[str] = []
    # After a blank line the next non-empty, non-timestamp line is a cue
    # identifier (numeric or string) — not spoken content. Track this.
    after_blank = True

    for line in text.splitlines():
        line = line.rstrip()

        # Blank line: mark that the next content line may be a cue identifier
        if not line:
            after_blank = True
            continue

        # Timestamp line: flush accumulated lines and start a new block
        ts_match = _TS_RE.match(line)
        if ts_match:
            if current_lines:
                raw_blocks.append((current_ts, current_lines))
            current_ts = ts_match.group(1)
            current_lines = []
            after_blank = False
            continue

        # Skip WEBVTT header, NOTE blocks, and fallback --> lines
        if line == "WEBVTT" or line.startswith("NOTE") or "-->" in line:
            after_blank = False
            continue

        # Skip cue identifiers (appear after blank, before timestamp)
        if after_blank:
            after_blank = False
            continue

        after_blank = False

        # Normalise speaker tags: <v Speaker>text</v> → [Speaker] text
        sp_match = _SP_RE.match(line)
        if sp_match:
            speaker = sp_match.group(1).strip()
            content = sp_match.group(2).strip()
            current_lines.append(f"[{speaker}] {content}")
        else:
            # Strip trailing </v> from multi-line cue continuation lines
            current_lines.append(re.sub(r"</v>\s*$", "", line))

    if current_lines:
        raw_blocks.append((current_ts, current_lines))

    if not raw_blocks:
        return []

    # Step 2: group blocks into WINDOW_SECONDS windows
    grouped: list[tuple[str, list[str]]] = []
    window_ts = raw_blocks[0][0]
    window_lines: list[str] = []

    for ts, lines in raw_blocks:
        elapsed = _ts_to_seconds(ts) - _ts_to_seconds(window_ts)
        if elapsed > WINDOW_SECONDS and window_lines:
            grouped.append((window_ts, window_lines))
            window_ts = ts
            window_lines = []
        window_lines.extend(lines)

    if window_lines:
        grouped.append((window_ts, window_lines))

    # Step 3: build fragment dicts (content computed once per fragment)
    fragments = []
    for ts, lines in grouped:
        if not lines:
            continue
        content = "\n".join(lines)
        fragments.append({
            "fragment_id": _frag_id(p.name, ts),
            "source_file": p.name,
            "source_type": "transcript",
            "client_slug": "",          # filled by _auto_ingest.py
            "content": content,
            "metadata": {
                "timestamp": ts,
                "speaker": None,        # mixed speakers within window
                "page": None,
                "slide": None,
                "sheet": None,
                "section": None,
            },
            "char_count": len(content),
            "ingested_at": "",          # filled by _auto_ingest.py
        })
    return fragments


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python parse_vtt.py <file.vtt>", file=sys.stderr)
        sys.exit(1)

    sys.stdout.reconfigure(encoding="utf-8")
    frags = parse(sys.argv[1])
    print(json.dumps(frags, indent=2, ensure_ascii=False))
    print(f"\n[{len(frags)} fragments from {sys.argv[1]}]", file=sys.stderr)
