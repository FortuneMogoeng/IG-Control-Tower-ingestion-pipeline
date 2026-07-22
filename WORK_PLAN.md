# Work Plan — IG Control Tower Ingestion

**Prepared by:** Fortune Mogoeng · 13 July 2026 · **Revised:** 22 July 2026
**Context:** This repo is now the canonical solution (see the 22 July pivot in `CLAUDE_HANDOVER.md`). Path A is live. This document covers Path B and Path C.

---

## Where We Are

| Phase | What | Status |
|-------|------|--------|
| Path A — local ingestion | Drop files in Evidence/, pipeline parses them | **Live and stable** (all 6 parsers present as of 22 July) |
| Path B — Azure trigger | Upload to Azure Blob, Function parses remotely | **Scaffolded — blocked on Azure access** |
| Path C — semantic search | Azure AI Search index over all fragments | **Future — triggers at 5th active client** |

---

## Path B — Azure Function Trigger (Immediate Next)

### What it does

Removes the need for a consultant to run the pipeline on their own laptop. A consultant uploads client files to an Azure Blob container; an Azure Function detects the upload and runs the parser automatically. Fragments land in Blob storage where the pipeline picks them up.

**Impact:** any consultant, any machine, no local Python setup.
**Status:** code scaffolded in `azure/document-parser-fn/`. Blocked only on Azure subscription access (owner: Wei).
**Estimated remaining effort:** deploy + wire Event Grid + smoke test = under a day once access is granted.

### What is already built (22 July)

| Piece | State |
|-------|-------|
| `azure/document-parser-fn/function_app.py` | Event Grid triggered Function. Reads slug from container name, parses via `parse_any.PARSERS`, writes `processed-{slug}/evidence/{stem}_fragments.jsonl`. Enforces the extension allowlist in code. |
| md/txt schema parity | Function uses the canonical sha256 parser, verified byte-identical to Path A. |
| `requirements.txt`, `host.json` | Runtime + parser deps, extension bundle v4. |
| `_download_azure_fragments()` in `_auto_ingest.py` | Client side — already implemented. Pulls `processed-{slug}/evidence/` into `Meeting-Notes/`. No-ops when the connection string is absent (Path A). |
| `azure/document-parser-fn/README.md` | Full deploy runbook: `az` CLI, Event Grid subscription, containers, FCA blob logging. |

### What remains (deploy time, needs Azure access)

1. Create Function App `document-parser-fn` (Python 3.11, Consumption, UK South).
2. Set `AZURE_STORAGE_CONNECTION_STRING` app setting (same value `db_sync.py` uses).
3. Vendor parsers (`cp -r ../../scripts/parsers ./parsers`) and publish.
4. Event Grid system topic on the existing storage account, `BlobCreated`, `subject-begins-with /blobServices/default/containers/intake-`, extension allowlist.
5. Create `intake-{slug}` / `processed-{slug}` container pairs per client.
6. Enable blob access logging to Log Analytics (zero code, FCA requirement).

All in `rg-ig-control-tower`, UK South. Cost: ~£2/month.

### Smoke tests after Path B deploys — Groups 6-7

| Group | Tests | Checks |
|-------|-------|--------|
| Group 6 — Azure Storage | 5 | Connection string valid, upsert idempotent, blob manifest upload, SQLite count >= 1,791 |
| Group 7 — Full E2E | 4 | VTT in → fragments out, multi-file client, incremental run, FCA traceability chain intact, Path A/B schema parity |

Run: `python -m pytest tests/smoke/ -v --run-integration`. **These can and should be written now**, ahead of deploy.

---

## Path C — Azure AI Search / Semantic RAG (Future)

### What it does

A semantic search index over all ingested fragments, so agents can query across all past evidence rather than only the current client's fragments.

**Trigger:** 5th active client (currently Downing LLP + VMO2 = 2).
**Effort:** ~1 week. **Dependency:** Azure AI Search S1 (~£80/month).

### What needs building

1. `chunk_and_embed.py` — chunk fragments, embed via Azure OpenAI, write to `evidence-index`.
2. Evidence Search stage — queries the index before opportunity extraction to surface cross-client patterns.
3. Azure AI Search S1 in `rg-ig-control-tower`, UK South.

Path A and Path B keep working unchanged; Path C is purely additive.

---

## Decisions Already Made

Locked. Do not revisit without a team discussion and an ADR.

| Decision | Reason |
|----------|--------|
| This repo is canonical; no upstream merge | 22 July pivot |
| Scripts (not AI) for parsing | Deterministic, FCA-traceable, free |
| Three-path architecture | Each path additive, none breaks a previous one |
| Fragment schema frozen | Changing it invalidates existing Azure ids |
| `fragment_id` = sha256(source+offset)[:16] | Stable across re-ingestion |
| No Fivetran/Airbyte | Neither handles VTT; £300+/month; evidence is documents |

---

## Outstanding Items (22 July)

| Item | Owner | Status |
|------|-------|--------|
| Azure subscription access for Path B | Wei / infra owner | Needed — the one blocker |
| Confirm VMO2 first pipeline run | Wei / other consultant | Parked (no local evidence) |
| Smoke tests Groups 6-7 | Engineering | Written (offline green; Azure tests run with --run-integration) |
| Consolidate db_sync/import_db/export_db into this repo | Fortune | Done 22 July — in scripts/db/, round-trip verified |
| Power BI dashboard over GenericOpportunities | Backlog | Unassigned, no Azure blocker |
| Path C trigger: 5th client | Fortune / leadership | Unscheduled |

---

*Inference Group Internal · revised 22 July 2026*
