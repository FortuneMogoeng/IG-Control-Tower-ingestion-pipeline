"""
Group 6 — Azure Storage + Path B round trip.

All tests here are `integration`: they need a live Azure connection and are
skipped unless `--run-integration` is passed and AZURE_STORAGE_CONNECTION_STRING
is set. They exercise the same contract the deployed document-parser-fn relies
on, plus the client-side downloader in _auto_ingest.

Offline unit checks of the Function's pure helpers live in test_group7_e2e.py
and test_pathb_unit.py; this file is only the live-Azure surface.
"""

import json
import os
import uuid

import pytest

import _auto_ingest
import core

pytestmark = pytest.mark.integration


@pytest.fixture
def blob_service():
    conn = os.environ.get(core.CONN_STR_ENV)
    if not conn:
        pytest.skip(f"{core.CONN_STR_ENV} not set")
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        pytest.skip("azure-storage-blob not installed")
    return BlobServiceClient.from_connection_string(conn)


def test_connection_string_valid(blob_service):
    """The connection string authenticates and lists containers."""
    # Consuming one item is enough to force the request to execute.
    next(iter(blob_service.list_containers(results_per_page=1)), None)


def test_blob_upload_is_idempotent(blob_service):
    """Re-uploading the same output blob with overwrite=True keeps one copy."""
    container = "processed-smoke-test"
    try:
        blob_service.create_container(container)
    except Exception:
        pass  # already exists
    name = core.output_blob_name(f"idem-{uuid.uuid4().hex}.vtt")
    client = blob_service.get_blob_client(container=container, blob=name)
    payload = core.fragments_to_jsonl([{"fragment_id": "x", "content": "y"}])

    client.upload_blob(payload, overwrite=True)
    client.upload_blob(payload, overwrite=True)  # must not raise

    matches = list(blob_service.get_container_client(container).list_blobs(name_starts_with=name))
    assert len(matches) == 1
    client.delete_blob()


def test_client_downloader_round_trip(blob_service, tmp_path):
    """
    Seed processed-{slug}/evidence/*.jsonl, then confirm
    _auto_ingest._download_azure_fragments pulls it into Meeting-Notes/.
    Mirrors what the deployed Function writes and the pipeline reads.
    """
    slug = "smoke-test"
    container = f"processed-{slug}"
    try:
        blob_service.create_container(container)
    except Exception:
        pass
    frag = {
        "fragment_id": "abc123def4567890",
        "source_file": "seed.vtt",
        "source_type": "transcript",
        "client_slug": slug,
        "content": "Seeded fragment for the Path B round-trip test.",
        "metadata": {"timestamp": "00:00:00", "speaker": None, "page": None,
                     "slide": None, "sheet": None, "section": None},
        "char_count": 47,
        "ingested_at": "",
    }
    blob_name = core.output_blob_name("seed.vtt")
    blob_service.get_blob_client(container=container, blob=blob_name).upload_blob(
        core.fragments_to_jsonl([frag]), overwrite=True
    )

    notes_dir = tmp_path / "Meeting-Notes"
    notes_dir.mkdir()
    count, errors = _auto_ingest._download_azure_fragments(slug, notes_dir)

    assert errors == []
    assert count >= 1
    written = list(notes_dir.glob("*_azure_parsed.md"))
    assert written and "Seeded fragment" in written[0].read_text(encoding="utf-8")

    # cleanup
    blob_service.get_blob_client(container=container, blob=blob_name).delete_blob()
