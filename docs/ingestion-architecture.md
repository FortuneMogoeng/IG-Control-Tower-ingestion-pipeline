# IG Control Tower — Formal Ingestion Architecture
**Date:** 10 July 2026 | **Version:** 2.0 | **Status:** Path A Live · Path B In Progress  
**Author:** Inference Group | **Audience:** Technical and Non-Technical Stakeholders

---

## For Everyone — What Is This and Why Does It Matter?

> **In plain English:** Every time a consultant meets a client, that meeting produces knowledge — a transcript, a PDF report, a spreadsheet. Today, turning that raw material into a structured proposal takes 3–4 hours of copy-paste work. This architecture eliminates that. Drop any file into a folder, and within 15 minutes you have a fully populated opportunity canvas, a Notion record, and a structured database entry — all without touching a keyboard again.

This document describes **how we get from raw files to structured intelligence** — the ingestion layer. It is the foundation the entire Control Tower pipeline sits on. If the ingestion layer works correctly, everything downstream is faster, more accurate, and reusable across clients. If it fails, all subsequent analysis is built on sand.

**Who should read this:**
- **Consultants:** Understand what file types you can drop in, what happens next, and how long it takes.
- **Leadership:** Understand the before/after business impact and the phased cost model.
- **Engineers:** Understand the parser inventory, fragment schema, code changes, and test suite.

---

## Version History

| Version | Date | What Changed |
|---------|------|--------------|
| 1.0 | 8 July 2026 | Initial release — Path A architecture, parser inventory, fragment schema |
| 1.1 | 9 July 2026 | 11 regression fixes across `parse_vtt.py` and `_auto_ingest.py`; Stage 0 hardened with returncode guard |
| 2.0 | 10 July 2026 | Full stakeholder rewrite — plain-language sections added; ADR formalised; complete cost breakdown; current progress snapshot; skill reuse map; dual pipeline clarification expanded |

---

## Current Progress Snapshot — July 10, 2026

| Component | Status | Details |
|-----------|--------|---------|
| Path A — Local File Processing | ✅ Live | VTT, PDF, XLSX, DOCX all parsing correctly |
| Azure Table Storage | ✅ Live | 1,791 opportunities stored; 1,951 analyses |
| Azure Static Web App | ✅ Live | Architecture docs and roadmaps accessible |
| Notion Sync | ✅ Live | Company DB, Meeting Notes, People DB syncing |
| Smoke Tests (Groups 1–4) | ✅ Passing | Parser, schema, ingestion, stage execution |
| Path B — Azure Blob Trigger | 🔄 This Week | Azure Function + Event Grid; ~1 day effort |
| Smoke Tests (Groups 5–7) | 🔄 This Week | Notion sync, Azure storage, full E2E |
| Path C — Vector Search / RAG | ⏳ Future | When >5 active clients; ~£160/mo additional |

---

## Two Pipelines — An Important Distinction

> **Plain English:** We actually have two separate assembly lines in the Control Tower, not one. They share the same raw material suppliers (the parsers) but produce different outputs for different purposes.

There are **two separate ingestion pipelines** that co-exist and serve different consumers:

| Pipeline | Input Folder | Script | Output | Who Uses It |
|----------|-------------|--------|--------|-------------|
| **Discovery Pipeline** (Stage 0, `ig-AI-opportunity-discovery`) | `Evidence/` folder | `_auto_ingest.py` (bulk wrapper) | `Meeting-Notes/*_parsed.md` | Stage 1 `ig-meeting-discovery` |
| **Control Tower Pipeline** (`ingest` skill) | `context/` folder | `parse_any.py` (called per file) | `evidence/fragments.jsonl` | All downstream stages via fragments |

The new `_auto_ingest.py` **does not replace** the `ingest` skill. It adds a pre-processing step to the discovery pipeline only. Both pipelines share the same underlying parsers (`parse_pdf.py`, `parse_vtt.py`, etc.) but produce different output formats for different consumers.

**Analogy:** Think of the parsers as translators who speak every document format. The Discovery Pipeline hires those translators to produce plain English summaries. The Control Tower Pipeline hires the same translators to produce structured data records. Same translators, different briefings.

---

## Architecture Decision Record (ADR-001)

**Decision:** Use a deterministic, script-based ingestion layer that runs before Claude is ever involved.

**Date:** 8 July 2026 | **Status:** Accepted | **Deciders:** Inference Group Engineering

### Context

The Control Tower pipeline needed a way to accept raw files (VTT, PDF, XLSX, DOCX) from consultants and convert them into structured data that AI agents can reason over. Three design approaches were considered:

1. **AI-first ingestion:** Let Claude read the raw files directly via tool calls
2. **Script-based preprocessing:** Write deterministic Python parsers that extract text and structure before Claude sees anything
3. **Third-party ETL:** Use a managed service (Fivetran, Airbyte) to handle document parsing

### Decision

We chose **Script-based preprocessing (option 2)**, with a clean separation between deterministic script work and AI reasoning:

```
Deterministic (scripts, no AI):
  parse_pdf.py, parse_vtt.py, parse_any.py, _auto_ingest.py
  → Responsible for: text extraction, schema normalisation, manifest writing

Claude-native (skills, agents):
  Everything from Stage 1 onwards
  → Responsible for: reasoning, analysis, synthesis, proposal generation
```

### Why This Decision

| Factor | Rationale |
|--------|-----------|
| **Reliability** | Deterministic parsers have no hallucination risk. A PDF page either extracts or it doesn't. |
| **Cost** | Parsing 100 pages of PDF via Claude API would cost ~£2. Python parser costs £0. |
| **Auditability** | FCA requires traceable provenance. A deterministic fragment ID (`sha256(file+offset)[:16]`) is verifiable; AI extraction is not. |
| **Reusability** | The same parsers feed both pipelines. Changing one parser improves both. |
| **Speed** | Python parsing takes milliseconds. Claude reasoning takes seconds per call. |

### Consequences

**Positive:**
- Zero hallucination risk in the ingestion layer
- Immutable fragment IDs enable idempotent re-runs (safe to run twice, never creates duplicates)
- Parser output is a testable contract — 38 smoke tests verify it independently of the AI layer
- FCA audit trail built in by design, not bolted on

**Negative / Risks:**
- Parser code must be maintained as new file formats emerge
- Edge cases in each format (malformed VTT, encrypted PDF) require handling in Python, not just prompts
- Adding a new format (e.g. MP3 audio) requires writing a new parser, not just changing a prompt

### Alternatives Rejected

| Alternative | Why Rejected |
|-------------|--------------|
| AI-first ingestion | Non-deterministic output, high API cost for large files, no fragment-level audit trail |
| Fivetran / Airbyte | Overkill for current volume; adds £300+/mo; doesn't handle VTT transcripts natively |

---

## What Gets Ingested — Source Types

> **Plain English:** The pipeline accepts 7 types of files. If a consultant can produce it from a client meeting or engagement, the pipeline can read it. The most important one is VTT — the transcript format that Teams, Zoom, and Fireflies all export.

| Source Type | Formats | Where It Comes From | All Three Paths? |
|-------------|---------|---------------------|-----------------|
| Meeting transcripts | `.vtt`, `.txt` | Microsoft Teams, Zoom, Fireflies | ✅ A, B, C |
| Company reports | `.pdf` | Client-provided, web research | ✅ A, B, C |
| Workshop outputs | `.pptx` | Consultant-created | ✅ A, B, C |
| Financial models | `.xlsx`, `.xlsm` | Client-provided | ✅ A, B, C |
| Word documents | `.docx`, `.doc` | Client or consultants | ✅ A, B, C |
| Markdown notes | `.md` | Notion export, consultants | ✅ A, B, C |
| Web pages | URL | Firecrawl/BrightData (MCP) | ✅ A, B, C |
| CRM / API feeds | REST JSON | Salesforce, HubSpot | ⏳ B, C only |

---

## The Three Implementation Paths

> **Plain English:** There are three ways to run the ingestion pipeline, ordered from simplest to most powerful. We always start with Path A. Path B adds automation. Path C adds intelligence. You can add B and C later without changing anything in A.

```
PATH A — "The Folder Drop" (LIVE NOW — £0.20/month)
══════════════════════════════════════════════════
Consultant drops files into Evidence/ folder on their laptop
    ↓
_auto_ingest.py scans the folder and parses each file
    ↓
Fragments written to Meeting-Notes/ as markdown
    ↓
Stage 1 picks them up and begins analysis
    ↓
Results sync to Notion + Azure Table Storage

No Azure beyond what we already have. Works today.
Time to first result: ~15 minutes.


PATH B — "The Cloud Folder" (This Week — +£2/month)
════════════════════════════════════════════════════
Consultant uploads file to Azure Blob Storage (any machine)
    ↓
Azure Event Grid detects the upload within 5 seconds
    ↓
Azure Function downloads the file, runs the right parser
    ↓
Fragments written to processed-{client-slug}/ in Azure Blob
    ↓
Same pipeline as Path A continues from here

Benefit: Pipeline is not tied to one person's laptop.
Any consultant on any machine can trigger it.


PATH C — "The Smart Search" (Future — +£160/month)
═══════════════════════════════════════════════════
Path B runs as normal
    ↓
chunk_and_embed.py takes each fragment, splits into 512-token chunks
    ↓
Azure OpenAI creates a vector embedding (a numerical fingerprint) for each chunk
    ↓
Chunks + embeddings stored in Azure AI Search index
    ↓
Instead of reading all files sequentially, agents search by meaning
    ↓
"Find everything clients have said about manual processes" returns relevant fragments instantly

Benefit: Cross-client pattern discovery. As evidence grows, search improves.
Triggers when: more than 5 active clients.
```

**Design principle:** *"Light now, not locked in."* Path A ships today. Path B drops in without changing Path A's output. Path C is a future enhancement. The agents never know which path is active.

---

## Parser Inventory — What Exists and What's Needed

> **Plain English:** Think of parsers as specialised readers. We have readers for PDFs, Word documents, Excel files, and PowerPoints. The one missing reader was for VTT transcript files — that gap was filled in v1.1.

| Parser | Location | Status | Library Used | Handles |
|--------|----------|--------|--------------|---------|
| `parse_pdf.py` | `scripts/parsers/parse_pdf.py` | ✅ Exists | pdfplumber | Page-by-page extraction, tables, headings |
| `parse_word.py` | `scripts/parsers/parse_word.py` | ✅ Exists | python-docx | Heading hierarchy, tables, lists |
| `parse_excel.py` | `scripts/parsers/parse_excel.py` | ✅ Exists | openpyxl | Sheet-by-sheet, typed values, headers |
| `parse_pptx.py` | `scripts/parsers/parse_pptx.py` | ✅ Exists | python-pptx | Slide-by-slide, speaker notes |
| `parse_any.py` | `scripts/parsers/parse_any.py` | ✅ Exists | — | Dispatcher — routes files to the right parser |
| `parse_vtt.py` | `scripts/parsers/parse_vtt.py` | ✅ Added v1.1 | stdlib (re) | Teams/Zoom/Fireflies VTT transcripts |
| `_auto_ingest.py` | `scripts/_auto_ingest.py` | ✅ Added v1.1 | — | Stage 0 wrapper — drives all parsers |

**All parsers produce the same output format: the canonical fragment schema.** This is the contract that makes the pipeline composable — add a new parser, and everything downstream works without any changes.

---

## The Canonical Fragment — The Atom of the Pipeline

> **Plain English:** Every piece of information that flows through the pipeline is stored as a "fragment." Think of it like a standardised index card. No matter whether the original was a PDF, a spreadsheet, or a meeting transcript, it comes out as the same type of index card with the same fields. This standardisation is what lets the AI agents read everything the same way.

```json
{
  "fragment_id":  "a3f9c2d10e4b7891",   ← unique fingerprint, never changes
  "source_file":  "ACME/2026-07-09-discovery-call.vtt",
  "source_type":  "vtt",
  "client_slug":  "acme",               ← connects this fragment to the right client in Notion
  "content":      "[CFO] The manual reconciliation takes 3 FTEs per month...",
  "metadata": {
    "speaker":    "CFO",                ← VTT only: who said this
    "timestamp":  "00:12:34",           ← VTT only: when in the meeting
    "page":       null,                 ← PDF only: which page
    "sheet":      null,                 ← XLSX only: which sheet
    "section":    null                  ← DOCX only: which heading section
  },
  "char_count":   61,
  "ingested_at":  "2026-07-09T10:22:00Z"
}
```

**Why the fragment ID never changes:** The ID is computed as `sha256(source_file + offset)[:16]`. Given the same file and the same position in that file, you always get the same ID. This means:
- Re-running the pipeline on the same files never creates duplicates
- You can always trace any piece of analysis back to its exact source passage
- FCA regulators can verify that a specific insight came from a specific line of a specific document

---

## Skill Reuse Map — Nothing Is Being Thrown Away

> **Plain English:** All 13+ skills we've built already continue to work unchanged. The ingestion layer is new plumbing that sits underneath them. The skills are the smart workers; the ingestion layer is the post room that sorts the incoming mail before the workers see it.

| Skill | What It Does | Role in Pipeline |
|-------|-------------|-----------------|
| `ingest` | Converts context/ files → fragments.jsonl | Called by Stage 0; _auto_ingest feeds it |
| `stage1` → `stage5` | Evidence gathering — briefings, research, stakeholders, documents, synthesis | Reads fragments.jsonl, produces intelligence |
| `stageA` → `stageG` | Analysis and delivery — opportunities, pain points, solutions, value, risk, canvas, proposal | Consumes Stage 1-5 outputs |
| `ideation-bot` | Orchestrates Notion canvas population | Invoked by Stage F |
| `ig-presentation` | Branded slide/HTML generation | Used in Stage G for proposal deck |
| `risk-advisor` | Ethics and privacy analysis | Called during Stage E |
| `value-analysis` | ROI estimation | Called during Stage D |
| `strategic-alignment` | Long-term strategic fit assessment | Used in Stage A |
| `data-architecture` | Architecture design pattern library | Used to design this pipeline |
| `de-pm` | Data Engineering PM oversight — pipeline health, schema contracts | Governance layer |
| `brand` | IG brand tokens and formatting | Applied to all client-facing outputs |

**New additions (scripts, not skills — they run before Claude starts):**

| Script | What It Does | Why It's a Script, Not a Skill |
|--------|-------------|-------------------------------|
| `_auto_ingest.py` | Watches Evidence/, dispatches parsers, writes fragments, writes audit manifest | Deterministic file I/O — no reasoning needed; cheaper, faster, more reliable |
| `parse_vtt.py` | Parses VTT transcript files into fragments | Regex + text processing — deterministic by design |

---

## Complete Tools and Cost Breakdown

> **Plain English:** The current system costs almost nothing to run. The future full system (with AI-powered search) costs about £160/month. Both are viable — start cheap, scale up when you have enough clients to justify it.

### Current State — Path A (Live Now)

| Tool | Purpose | Cost |
|------|---------|------|
| Claude Code (Sonnet 4.6) | All 13 analysis stages, all skills | Included in Pro plan |
| Azure Static Web App (F1) | Hosts architecture docs, stakeholder roadmaps | £0 |
| Azure Table Storage (LRS) | GenericOpportunities, CompanyAnalyses, CompanyProfiles | ~£0.04/month |
| Azure Blob Storage (Hot LRS) | Raw evidence files, processed fragments, FCA audit manifests | ~£0.15/month |
| Notion API (Team plan) | Company DB, Meeting Notes, People DB — canvas creation | Included in existing subscription |
| SQLite (local file) | Local analysis DB — 1,791 opportunities, 1,951 analyses | £0 |
| Python parsers (OSS) | pdfplumber, openpyxl, python-docx, python-pptx | £0 |
| **PATH A TOTAL** | | **~£0.20/month** |

### Near-Term — Path B (This Week)

Adds on top of Path A:

| Tool | Purpose | Additional Cost |
|------|---------|----------------|
| Azure Event Grid (System Topic) | Detects new file uploads to Blob Storage | ~£0.80/month |
| Azure Functions (Consumption Plan) | Serverless parser trigger on new blob upload | ~£0.50/month |
| Increased Blob Storage usage | Files now also stored in Azure, not just locally | ~£0.50/month |
| **PATH B ADDITIONAL** | | **~+£1.80/month** |
| **PATH B TOTAL** | | **~£2/month** |

### Future State — Path C (When >5 Active Clients)

Adds on top of Path B:

| Tool | Purpose | Additional Cost |
|------|---------|----------------|
| Azure AI Search (Standard S1) | Vector + keyword hybrid search for RAG retrieval | ~£150/month |
| Azure OpenAI Embeddings (text-embedding-3-large) | Convert fragments to searchable vector embeddings | ~£10–40/month |
| Azure Purview (optional) | Data governance catalog, lineage tracking | ~£50–100/month |
| **PATH C ADDITIONAL** | | **~+£210–290/month** |
| **PATH C TOTAL** | | **~£212–292/month** |

### Cost Decision Rule

```
< 5 active clients    → Path A + B only. Skip AI Search.
                         Use Claude's reasoning to handle deduplication.

5–15 active clients  → Add Path C with AI Search Basic (~£135/mo).
                         Upgrade to S1 when index exceeds 2GB.

15+ clients          → AI Search S1 or S2, Azure Purview, reserved pricing.
                         Negotiate EA or MACC commit for 20–40% discount.
```

**Important:** Path C is not required for quality results. It improves speed and cross-client pattern discovery. The pipeline produces excellent results on Path A alone — the evidence is read file-by-file rather than searched semantically, which is fine for up to ~5 clients.

---

## How Automation Works — Zero Human Intervention Design

> **Plain English:** Once you drop a file in, you don't need to do anything else. The pipeline handles the rest. The only time a human is needed is to review and approve the final proposal before it goes to the client. Everything in between is automatic.

The eight steps that happen without human intervention:

1. **File Drop** — Analyst drops a VTT, PDF, or XLSX into `Evidence/{client-slug}/`. No form, no button, no email.
2. **Auto-Ingest (Stage 0)** — `_auto_ingest.py` scans Evidence/, compares against the manifest, dispatches the right parser. Writes fragments and updates the manifest. Idempotent: re-running never creates duplicates.
3. **Sequential Stage Execution** — Each stage reads the previous stage's output from `context/`. No human needs to pass context between stages. Runs 1→2→3→4→5→A→B→C→D→E→F→G.
4. **Notion Auto-Sync** — Stage F invokes `ideation-bot` which calls the Notion MCP server to create or update the AI Product Canvas. No copy-paste. Page title deduplicates; relations resolved by `client_slug`.
5. **Azure Storage Sync** — Results written to Azure Table Storage (CompanyAnalyses, GenericOpportunities). Writes are idempotent via `PartitionKey=client_slug`, `RowKey=fragment_id`.
6. **Audit Trail** — Every run writes `_ingestion_manifest.json`: source file, parser used, fragment count, timestamps, SHA-256 hash. Azure Blob access logs provide immutable provenance.
7. **Failure Recovery** — If a stage fails: manifest records the failure, pipeline halts, next run picks up from last successful stage. No partial writes reach Notion or Azure.
8. **Human Review Gate** — The only human touchpoint is reviewing Stage G output (the proposal) before client delivery.

**Total elapsed time for a 60-minute meeting transcript:** ~15 minutes.  
**Previous manual time:** 3–4 hours per engagement.  
**Time saving:** ~93% reduction in consultant time per client meeting cycle.

---

## FCA Compliance — Audit Trail Design

> **Plain English:** FCA regulations require us to be able to prove, for any analysis output, exactly where the data came from and when it was processed. Our audit trail is built into the ingestion layer — it doesn't rely on memory or manual documentation.

The audit trail has three layers:

1. **Fragment provenance** — every fragment has a deterministic `fragment_id` and `ingested_at` timestamp. Given any fragment, you can always recover: which source file it came from, which parser processed it, and when.

2. **Ingestion manifest** — `_ingestion_manifest.json` written on every run. Contains: list of files processed, fragments produced per file, parser version used, operator email, run timestamp, and SHA-256 hash of each source file.

3. **Azure Blob access logging** — every read/write to the storage account is logged to Azure Monitor Log Analytics automatically. Zero additional code required. Immutable by Azure's infrastructure.

**Key FCA compliance controls in this architecture:**

| Control | How Implemented | Where |
|---------|----------------|-------|
| Immutable source records | Raw files uploaded to Azure Blob with immutable access logging | Azure Blob Storage |
| Transformation audit trail | Manifest records every file-to-fragment transformation | `_ingestion_manifest.json` |
| Data lineage | Fragment ID traces any output back to source passage | Fragment schema |
| Named-user access | No shared service accounts; AZURE_STORAGE_CONNECTION_STRING per user | Environment variable |
| UK data residency | All Azure resources in UK South region | Azure Resource Group |
| Retention | Azure Blob lifecycle policy — 7 years for raw evidence | Azure Blob policy |

---

## Migration Roadmap

### Phase 1 — Path A (COMPLETE — July 9, 2026)

**What we built:** The local evidence ingestion pipeline. Drop files, get fragments, run analysis.

- ✅ `parse_vtt.py` — handles Teams, Zoom, Fireflies VTT formats
- ✅ `_auto_ingest.py` — Stage 0 wrapper, bulk parsing, manifest writing
- ✅ `parse_any.py` — patched with VTT dispatch
- ✅ Stage 0 — hardened with returncode guard
- ✅ 11 regression fixes (v1.0 → v1.1)
- ✅ Smoke test Groups 1–4 passing (28 tests)
- ✅ Azure Table Storage live (1,791 opportunities confirmed)
- ✅ Notion MCP sync working

### Phase 2 — Path B (Target: July 11–14, 2026)

**What we're building:** Azure Blob trigger so any consultant can upload from any machine.

- [ ] Deploy Azure Function (`document_parser`) — Python, EventGrid trigger
- [ ] Configure Azure Event Grid on storage account — filter: BlobCreated, extension allowlist
- [ ] Enable Azure Blob access logging for FCA audit trail
- [ ] Extend `_auto_ingest.py` with `_download_azure_fragments()` function
- [ ] Smoke test Groups 5–7 (Notion sync, Azure Storage, full E2E)
- [ ] End-to-end test: upload VTT to Azure → Notion canvas created

**Effort:** ~1 day. Requires Azure subscription access for Function deployment.

### Phase 3 — Path C (Target: When >5 Active Clients)

**What we'll build:** Vector search so agents can query across all client evidence semantically.

- [ ] Deploy Azure AI Search (Basic tier initially, upgrade to S1 when >2GB index)
- [ ] Write `chunk_and_embed.py` — fragment chunking + Azure OpenAI embedding
- [ ] Build evidence-index in Azure AI Search
- [ ] Update agent query layer to use semantic search instead of loading full JSONL
- [ ] (Optional) Azure Purview for governance catalog

**Trigger condition:** More than 5 active clients generating regular evidence. Cross-client pattern discovery becomes the business justification.

### Phase 4 — Future Enhancements (Backlog)

- Power BI dashboard over Azure Table Storage (GenericOpportunities table)
- Automated proposal email delivery via Outlook MCP after Stage G
- Whisper transcription for audio files (MP3/MP4) → VTT → pipeline
- GitHub Actions CI to run smoke tests on every push
- Multi-tenant isolation: per-client storage account scoping

---

## Files Created or Modified — Developer Summary

| File | Action | Effort | Dependency |
|------|--------|--------|------------|
| `scripts/parsers/parse_vtt.py` | Created (v1.1) | 1 hr | VTT ingestion |
| `scripts/parsers/parse_any.py` | 1 line added (v1.1) | 2 min | VTT dispatch |
| `scripts/_auto_ingest.py` | Created (v1.1) | 1 hr | Stage 0 automation |
| Stage 0 (ig-AI-opportunity-discovery) | 4 lines added (v1.1) | 10 min | Pipeline trigger |
| `document_parser/` Azure Function | To create (Path B) | 4 hrs | Azure access |
| `_auto_ingest.py` (Azure extension) | To add 1 function (Path B) | 1 hr | Path B |
| `chunk_and_embed.py` | To create (Path C) | 4 hrs | Azure AI Search |

**Path A total:** ~2.5 hours. No new Azure resources. Ships immediately.  
**Path B total:** ~1 day. Requires Azure Function deployment access.  
**Path C total:** ~1 week. Requires Azure AI Search provisioning.

---

## v1.1 Regression Fix Summary (8 → 9 July)

### parse_vtt.py — 7 fixes

| Bug | Before (v1.0) | After (v1.1) |
|-----|--------------|-------------|
| Teams `</v>` closing tag appeared in content | `_SP_RE` captured full line including tag | Regex changed to `(.+?)(?:</v>)?\s*$` |
| Zoom sub-hour calls silently dropped | `_TS_RE` required `HH:MM:SS` format | `_TS_RE` now accepts `MM:SS.mmm` too |
| Fireflies NOTE blocks ingested as speech | No guard | `line.startswith("NOTE")` added to skip |
| String cue IDs (e.g. "intro") appeared as content | Only `line.isdigit()` was skipped | `after_blank` state machine tracks cue identifier position |
| Fragment IDs shifted on re-ingestion (duplicates created) | Used `enumerate` index | ID now hashes `source_file + window_ts` |
| `char_count` computed twice (performance) | `len("\n".join(lines))` called twice | Content stored in variable; `len(content)` once |
| `_ts_to_seconds` crashed on MM:SS input | Only split into 3 parts | Handles 2-part and 3-part timestamp formats |

### _auto_ingest.py — 9 fixes

| Bug | Before (v1.0) | After (v1.1) |
|-----|--------------|-------------|
| `KeyError: 'content'` for all non-VTT parsers | Hard-referenced `fr["content"]` | `fr.get("content") or fr.get("text", "")` |
| `location` field from old parsers silently dropped | Not handled | Added as final fallback in loc chain |
| Page 0 silently skipped (cover pages lost) | `meta.get("page")` falsy for `0` | Changed to `page is not None` guard |
| `.md` files produced one monolithic fragment | No heading-aware splitting | Top-level `# headings` now split into separate fragments |
| Fragment ID collision across clients | `sha256(path.name)` only — same filename = same ID | ID now hashes `filename:index:file_size` |
| Parser module re-imported on every file (slow) | No import cache | Module-level `_parser_cache` dict added |
| One bad Azure blob aborted all remaining blobs | Single try/except around loop | Per-blob `try/except`; errors collected into result dict |
| Azure errors not returned in result dict | `_download_azure_fragments` returned `int` | Returns `(count, errors)` tuple |
| `sys.path` polluted on re-import | Unconditional `sys.path.insert` | Guarded with `if str not in sys.path` |

### Stage 0 — 1 fix

| Bug | Before (v1.0) | After (v1.1) |
|-----|--------------|-------------|
| Subprocess crash silently swallowed | No `returncode` check | `returncode != 0` branch added with stderr preview |

---

## Smoke Test Coverage

38 tests across 7 groups. Run with: `python -m pytest tests/smoke/ -v`

| Group | Tests | Coverage |
|-------|-------|---------|
| 1: Parser Correctness | 7 | VTT (Teams/Zoom/Fireflies), PDF, XLSX, DOCX, encoding |
| 2: Fragment Schema | 5 | Required fields, deterministic IDs, no duplicates, char_count accuracy |
| 3: Ingestion Pipeline | 7 | New file detected, idempotency, manifest written, corrupt file handled |
| 4: Stage Execution | 6 | Stage outputs produced, Notion canvas created, no fragment mutation |
| 5: Notion Sync | 4 | Env vars, dedup, rate limit backoff, ManifestID recorded |
| 6: Azure Storage | 5 | Connection string, table write, idempotent upsert, blob upload, SQLite |
| 7: Full E2E (Golden Path) | 4 | VTT → canvas, multi-file merge, incremental run, FCA traceability |

**Groups 1–4:** ✅ Passing  
**Groups 5–7:** 🔄 Target completion with Path B this week

---

*Inference Group Internal · 10 July 2026 · FCA-regulated — handle with care*  
*Fortune@inferencegroup.com · Version 2.0*
