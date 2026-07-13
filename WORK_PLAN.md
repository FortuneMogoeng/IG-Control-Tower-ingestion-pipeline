# Work Plan — IG Control Tower Ingestion Phases

**Prepared by:** Fortune Mogoeng · 13 July 2026  
**Context:** Fortune is OOO 13–20 July. Path A is live. This document covers what comes next.

---

## Where We Are

| Phase | What | Status |
|-------|------|--------|
| Path A — local ingestion | Drop files in Evidence/, pipeline parses them | **Live and stable** |
| Path B — Azure trigger | Upload files to Azure Blob, pipeline parses them remotely | **Next — ~1 day** |
| Path C — semantic search | Azure AI Search index over all fragments | **Future — ~1 week, triggers at >5 clients** |

---

## Path B — Azure Function Trigger (Immediate Next)

### What it does

Removes the requirement for a consultant to have the pipeline running on their own laptop. Instead, any consultant uploads client files to an Azure Blob container. An Azure Function detects the upload and runs the parser automatically. The fragments land in Azure Blob storage where the pipeline picks them up.

**Impact:** Any consultant, any machine, no local Python setup needed.  
**Estimated effort:** 1 working day.  
**Dependencies:** Azure subscription access (to deploy the Function App and Event Grid).

### What needs to be built

#### 1. Azure Function — `document-parser`

A serverless Python function. It triggers when a file is uploaded to `intake-{client-slug}/` in Azure Blob Storage.

**Behaviour:**
- Receives a `BlobCreated` event from Azure Event Grid
- Reads the client slug from the container name (`intake-downing-llp` → `slug = "downing-llp"`)
- Calls the correct parser using the existing `parse_any.PARSERS` dict — no new parsing code needed
- Writes `evidence/{stem}_fragments.jsonl` to `processed-{client-slug}/` container

**Key point:** The existing parsers (`parse_vtt.py`, `parse_pdf.py`, etc.) do not need to change. The Function just calls them the same way `_auto_ingest.py` does.

Connection string: `AZURE_STORAGE_CONNECTION_STRING` — already in use by `db_sync.py`.

#### 2. Azure Event Grid system topic

One system topic on the existing storage account. Filter: `BlobCreated` events only, with an extension allowlist: `.vtt`, `.pdf`, `.xlsx`, `.docx`, `.pptx`, `.md`, `.txt`. No per-client configuration.

#### 3. Update `_auto_ingest.py` — add Azure download

Add one function: `_download_azure_fragments()`. Already stubbed in the current `_auto_ingest.py` — it checks for `AZURE_STORAGE_CONNECTION_STRING` and if set, pulls pre-processed fragments from `processed-{client-slug}/evidence/` into `Meeting-Notes/`.

This makes `_auto_ingest.py` backward-compatible: it works in both Path A mode (local only) and Path B mode (Azure + local).

#### 4. Enable Blob access logging

Turn on diagnostic logging on the storage account → Log Analytics Workspace. Zero code. This gives FCA the immutable file access log it requires.

### Azure resources needed

| Resource | Name | SKU/tier |
|----------|------|----------|
| Blob containers | `intake-{client-slug}` (one per client) | Standard LRS |
| Blob containers | `processed-{client-slug}` (one per client) | Standard LRS |
| Event Grid system topic | On the existing storage account | Standard |
| Azure Function App | `document-parser-fn` | Consumption plan |
| Log Analytics Workspace | Existing or new | Pay-as-you-go |

All resources go in `rg-ig-control-tower`, UK South region.

**Estimated cost:** ~£2/month total for Path B.

### Smoke tests to run after Path B deploys

These are the remaining tests from the 38-test smoke suite (Groups 5–7):

| Group | Tests | What they check |
|-------|-------|-----------------|
| Group 5 — Notion sync | 4 tests | Env vars present, no duplicate pages on re-run, rate limit backoff works, ManifestID recorded |
| Group 6 — Azure Storage | 5 tests | Connection string valid, table write succeeds, upsert is idempotent, blob manifest upload, SQLite count ≥ 1,791 |
| Group 7 — Full E2E | 4 tests | VTT in → Notion canvas out in <15 min, multi-file client, incremental run, FCA traceability chain intact |

Run with: `python -m pytest tests/smoke/ -v --run-integration`

---

## Path C — Azure AI Search / Semantic RAG (Future)

### What it does

Adds a semantic search index over all ingested fragments. Instead of each pipeline run only seeing its own client's fragments, agents can query across all past evidence for similar opportunities, patterns, and risks.

**Trigger:** When the fifth active client comes on board (currently: Downing LLP + VMO2 = 2 active).  
**Estimated effort:** ~1 week.  
**Dependencies:** Azure AI Search S1 tier provisioned (~£80/month).

### What needs to be built

1. `chunk_and_embed.py` — splits fragments into smaller chunks, generates embeddings via Azure OpenAI, writes to Azure AI Search `evidence-index`
2. Evidence Search stage — new pipeline stage that queries the index before Stage A (opportunity extraction) to surface cross-client patterns
3. Azure AI Search S1 provisioned in `rg-ig-control-tower`, UK South

**Key point:** Path A and Path B continue working exactly as they do now. Path C is purely additive — it adds a search layer on top, it does not replace the existing ingestion.

---

## Decisions Already Made

These decisions are locked. Do not revisit without a full team discussion and an Architecture Decision Record (ADR).

| Decision | Reason |
|----------|--------|
| Scripts (not AI) for file parsing | Deterministic, FCA-traceable, free to run |
| Three-path architecture | Each path is additive, no path breaks a previous one |
| Fragment schema is frozen (13 fields) | Changing it would invalidate all existing IDs in Azure |
| `fragment_id` = sha256(filename+offset)[:16] | Stable across re-ingestion, FCA-verifiable |
| No Fivetran/Airbyte | Neither handles VTT; both add £300+/month; evidence is documents not DB tables |

---

## Outstanding Items (as of 13 July)

| Item | Owner | Status |
|------|-------|--------|
| Confirm VMO2 first pipeline run succeeded | Fortune (on return 20 July) | Unknown |
| Azure subscription access for Path B deployment | Team lead / infra owner | Needs confirmation |
| Smoke tests Groups 5–7 | Engineering | Blocked on Path B |
| Power BI dashboard over GenericOpportunities | Backlog | Unassigned |
| Path C trigger: when does 5th client arrive? | Fortune / leadership | Unscheduled |

---

*Inference Group Internal · 13 July 2026*
