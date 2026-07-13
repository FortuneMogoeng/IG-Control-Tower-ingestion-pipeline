# OOO Email — Final Draft

**To:** Wei  
**BCC:** Richard, Karin  
**From:** Fortune Mogoeng  
**Subject:** Out of Office — 13–20 July | Control Tower Ingestion Update + Next Steps

---

Hi Wei,

I will be out of office from **13 July to 20 July** (returning Monday 21 July). I wanted to make sure you have full visibility of where things stand so nothing is blocked while I am away.

---

## What Was Completed This Week (7–13 July)

### Ingestion Pipeline — Path A

The main piece of work this week was removing the biggest bottleneck in the Control Tower pipeline. Previously, consultants had to manually convert transcripts, PDFs, and slide decks into a format the agents could read. That is now fully automated.

**What was built:**

- `parse_vtt.py` — reads meeting transcripts from Teams, Zoom, and Fireflies automatically. A consultant drops a `.vtt` file into an `Evidence/` folder and the pipeline handles the rest.
- `_auto_ingest.py` — a Stage 0 wrapper that scans the `Evidence/` folder before any AI agents run. It dispatches the correct parser for every supported file type: transcripts, PDFs, Excel models, Word documents, and PowerPoints.

The pipeline now processes all evidence files automatically. No other part of the pipeline changes — all 19 skills, all agent prompts, all stages are untouched.

**Status:** Stable. 5/5 tests passed this morning, including against a real Teams call recording.

**One fix made today (v1.2):** During a last-minute test, I found and fixed a bug where multi-line speaker turns in Teams transcripts left a stray formatting tag in the output. This is resolved in the version now in the repo.

### Architecture Documentation

The full architecture is documented and accessible at:

**`https://github.com/FortuneMogoeng/IG-Control-Tower-ingestion-pipeline`**

This includes:
- A plain-English walkthrough of how the pipeline works end to end (README.md)
- The formal architecture spec (docs/ingestion-architecture.md)
- Step-by-step merge instructions for whoever applies this to the main codebase (MERGE_GUIDE.md)
- The work plan for Path B — the next phase (WORK_PLAN.md)

**1,791 opportunities** are currently live in Azure Table Storage across Downing LLP and VMO2.

---

## What Needs to Happen While I Am Away

### Merge to `ig-plugins` (30 minutes, low risk)

The ingestion changes are ready but I cannot push directly to the main branch. Someone with write access needs to apply them.

Everything needed is in the repo above:

- `MERGE_GUIDE.md` — exact step-by-step instructions
- `PATCHES.md` — the precise code changes (3 new files to copy in, one 12-line edit to an existing file)
- `tests/fixtures/` — test files to verify the merge worked
- `tests/TEST_RESULTS.md` — what a passing test looks like

The changes are additive only. No existing files are removed or altered.

### Path B — Azure Function (Next Sprint)

Once the merge is done, the next engineering task is **Path B**: an Azure Function that lets any consultant upload files directly to Azure Blob Storage and trigger the pipeline remotely — no local setup required.

Estimated effort: **1 working day**. The full technical spec, required Azure resources, and smoke tests are all in `WORK_PLAN.md` in the repo.

The main dependency is Azure subscription access to deploy a Function App and Event Grid topic.

---

## If Something Is Urgent

Wei — you have full context on the pipeline and the repo. The complete technical handover is at `JULY\HANDOVER-13-July-2026.md` in the shared OneDrive folder.

I will pick up any remaining items when I return on 21 July.

---

Best,  
Fortune Mogoeng  
Inference Group  
Fortune@inferencegroup.com
