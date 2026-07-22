"""
Offline unit tests for the Path B Function's pure helpers (core.py).
No Azure connection required.
"""

import pytest

import core


@pytest.mark.parametrize("container,expected", [
    ("intake-downing-llp", "downing-llp"),
    ("intake-vmo2", "vmo2"),
    ("processed-downing-llp", ""),   # not an intake container
    ("random", ""),
    ("intake-", ""),                 # prefix only -> empty slug
])
def test_slug_from_container(container, expected):
    assert core.slug_from_container(container) == expected


@pytest.mark.parametrize("url,expected", [
    ("https://acct.blob.core.windows.net/intake-vmo2/kickoff.vtt",
     ("intake-vmo2", "kickoff.vtt")),
    ("https://acct.blob.core.windows.net/intake-x/sub/deck.pptx",
     ("intake-x", "sub/deck.pptx")),
    ("https://acct.blob.core.windows.net/onlycontainer", None),
])
def test_container_blob_from_url(url, expected):
    assert core.container_blob_from_url(url) == expected


def test_url_with_encoded_spaces():
    url = "https://acct.blob.core.windows.net/intake-vmo2/AI%20Catch%20Up.vtt"
    assert core.container_blob_from_url(url) == ("intake-vmo2", "AI Catch Up.vtt")


def test_output_blob_name_round_trips_with_downloader_stem():
    """
    output_blob_name must be reversible by the downloader, which does
    Path(name).stem.replace('_fragments', '').
    """
    from pathlib import Path
    out = core.output_blob_name("kickoff.vtt")
    assert out == "evidence/kickoff_fragments.jsonl"
    recovered = Path(out).stem.replace("_fragments", "")
    assert recovered == "kickoff"


def test_allowlist_covers_all_supported_types():
    for ext in (".vtt", ".pdf", ".docx", ".xlsx", ".pptx", ".md", ".txt"):
        assert ext in core.ALLOWED_EXTENSIONS
    assert ".exe" not in core.ALLOWED_EXTENSIONS
    assert ".zip" not in core.ALLOWED_EXTENSIONS
