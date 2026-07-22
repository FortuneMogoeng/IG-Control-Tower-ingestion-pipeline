"""
document-parser-fn — Path B Azure Function for IG Control Tower ingestion.

Triggers on a BlobCreated event (via Event Grid) when a consultant uploads a
client file to `intake-{client-slug}/` in Azure Blob Storage. Runs the existing
deterministic parser for that file type and writes the fragments as JSONL to
`processed-{client-slug}/evidence/{stem}_fragments.jsonl`.

The pipeline consumer `_auto_ingest._download_azure_fragments()` then pulls those
JSONL files into Meeting-Notes/ on the next run. No consultant needs the pipeline
running on their own laptop.

This module is a thin Event Grid + Blob I/O shell. All parsing logic lives in
core.py, which is SDK-free and unit tested (tests/smoke/).

Deploy: see README.md. `parsers/` must be vendored alongside this file at deploy
time (the deploy step copies ../../scripts/parsers here).
"""

import logging
import os
import tempfile
from pathlib import Path

import azure.functions as func

import core

app = func.FunctionApp()


@app.function_name(name="documentParser")
@app.event_grid_trigger(arg_name="event")
def document_parser(event: func.EventGridEvent) -> None:
    """
    Handle a Storage BlobCreated event.

    Event subject / url points at:
      /blobServices/default/containers/intake-downing-llp/blobs/kickoff.vtt
    """
    blob_url = event.get_json().get("url", "")
    logging.info("BlobCreated event for: %s", blob_url)

    parsed = core.container_blob_from_url(blob_url)
    if parsed is None:
        logging.warning("Cannot parse container/blob from url: %s", blob_url)
        return
    container, blob_name = parsed

    client_slug = core.slug_from_container(container)
    if not client_slug:
        logging.info("Container %s is not an intake-* container; ignoring.", container)
        return

    ext = Path(blob_name).suffix.lower()
    if ext not in core.ALLOWED_EXTENSIONS:
        logging.info("Extension %s not in allowlist; ignoring %s.", ext, blob_name)
        return

    conn_str = os.environ.get(core.CONN_STR_ENV)
    if not conn_str:
        logging.error("%s not configured; cannot process blob.", core.CONN_STR_ENV)
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
            fragments = core.parse_file(local)
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
    out_name = core.output_blob_name(blob_name)
    dst_container = f"processed-{client_slug}"
    svc.get_blob_client(container=dst_container, blob=out_name).upload_blob(
        core.fragments_to_jsonl(fragments), overwrite=True
    )

    logging.info("Wrote %d fragment(s) to %s/%s", len(fragments), dst_container, out_name)
