# Ingestion Pipeline — Last-Minute Test Results

**Date:** 13 July 2026 09:55  
**Tester:** Fortune Mogoeng (automated via PowerShell)  
**Parser version:** parse_vtt.py v1.2  
**Python:** 3.14.6

---

## Summary

5/5 tests passed. A v1.2 bug was found and fixed during this run (see below).

---

## Test Results

### Fixture Tests

| Test | File | Fragments | `</v>` Tags | Result |
|------|------|-----------|-------------|--------|
| Teams multi-line cues | `real-teams.vtt` | 6 | None | **PASS** |
| Zoom sub-hour (MM:SS) | `zoom-format.vtt` | 2 | None | **PASS** |
| Fireflies export | `fireflies-test.vtt` | 1 | None | **PASS** |
| String cue identifiers | `string-cues.vtt` | 1 | None | **PASS** |

### Real Meeting Test

| Test | File | Fragments | `</v>` Tags | Result |
|------|------|-----------|-------------|--------|
| Teams real call | `AI Control Tower Catch Up.vtt` | 6 | None | **PASS** |

---

## Bug Found and Fixed — v1.2 (13 July)

**Bug:** `</v>` closing tags appeared in fragment content for Teams VTT files with multi-line cue content.

**Root cause:** Teams exports can span a single speaker turn across multiple lines, like this:

```
<v Fortune Mogoeng>I'm sorry,
I haven't had a chance to look at this.</v>
```

The `_SP_RE` regex in `parse_vtt.py` only matched the opening `<v Speaker>` line. Continuation lines (like the second line above) fell through to the `else` branch unchanged — including the trailing `</v>`.

**Fix:** One-line change in `parse_vtt.py` at line 96:

```python
# Before (v1.1)
else:
    current_lines.append(line)

# After (v1.2)
else:
    # Strip trailing </v> from multi-line cue continuation lines
    current_lines.append(re.sub(r"</v>\s*$", "", line))
```

**Tests that caught it:** `real-teams.vtt` and `AI Control Tower Catch Up.vtt` — both produced `</v>` tags in v1.1, both clean in v1.2.

---

## How to Re-Run These Tests

```bash
# All fixtures
python scripts/parsers/parse_vtt.py tests/fixtures/real-teams.vtt
python scripts/parsers/parse_vtt.py tests/fixtures/zoom-format.vtt
python scripts/parsers/parse_vtt.py tests/fixtures/fireflies-test.vtt
python scripts/parsers/parse_vtt.py tests/fixtures/string-cues.vtt

# For each: expected output is JSON array, no </v> in content, at least 1 fragment

# Auto-ingest wrapper
mkdir test-run\Evidence
copy tests\fixtures\real-teams.vtt test-run\Evidence\
python scripts/_auto_ingest.py .\test-run --client-slug test
# Expected: Meeting-Notes\ folder with real-teams_parsed.md inside
```

---

*Inference Group Internal · 13 July 2026*
