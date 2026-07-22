# document-parser-fn — Path B (Azure Function)

Server side of Path B. Consultants upload a client file to `intake-{slug}/` in
Azure Blob Storage; this Function parses it deterministically and writes fragments
to `processed-{slug}/evidence/{stem}_fragments.jsonl`. The pipeline's
`_auto_ingest._download_azure_fragments()` (already implemented) pulls them on the
next run. No consultant needs the pipeline on their own laptop.

**Status:** scaffolded 22 July 2026, not yet deployed. Blocked on Azure
subscription access (owner: Wei). Local code is deploy-ready.

Cost when live: ~£2/month. Region: UK South. Resource group: `rg-ig-control-tower`.

---

## Files

| File | Purpose |
|------|---------|
| `function_app.py` | Event Grid triggered function (Python v2 model) |
| `requirements.txt` | Runtime + parser dependencies |
| `host.json` | Functions host config (extension bundle v4) |
| `parsers/` | **Vendored at deploy time** — not committed. See build step. |

The Function reuses `../../scripts/parsers` unchanged. It does not duplicate any
parsing logic except the canonical `.md/.txt` parser, which is kept byte-for-byte
consistent with `_auto_ingest._parse_plain_text` so Path A and Path B emit
identical fragments (sha256 ids, content/metadata schema).

---

## Build (vendor the parsers)

The parsers must sit next to `function_app.py` at publish time:

```bash
# from azure/document-parser-fn/
cp -r ../../scripts/parsers ./parsers
```

Add `parsers/` to `.funcignore`'s inverse — i.e. ensure it is NOT ignored. Do not
commit `parsers/` to git; it is a build artefact copied from the source of truth.

---

## Deploy

Prerequisites: `az` CLI logged in, Azure Functions Core Tools v4, access to
`rg-ig-control-tower`. The storage account already exists (used by `db_sync.py`).

```bash
# 1. Create the Function App (Python 3.11, Consumption, UK South)
az functionapp create \
  --resource-group rg-ig-control-tower \
  --name document-parser-fn \
  --storage-account <existing-storage-account> \
  --consumption-plan-location uksouth \
  --runtime python --runtime-version 3.11 \
  --functions-version 4 --os-type Linux

# 2. App setting: the connection string the Function reads (same as db_sync.py)
az functionapp config appsettings set \
  --resource-group rg-ig-control-tower --name document-parser-fn \
  --settings "AZURE_STORAGE_CONNECTION_STRING=<conn-str>"

# 3. Publish (run the build step above first)
func azure functionapp publish document-parser-fn --python
```

### Event Grid — route BlobCreated to the Function

```bash
# System topic on the existing storage account (once)
az eventgrid system-topic create \
  --resource-group rg-ig-control-tower \
  --name ig-storage-topic \
  --source /subscriptions/<sub>/resourceGroups/rg-ig-control-tower/providers/Microsoft.Storage/storageAccounts/<acct> \
  --topic-type Microsoft.Storage.StorageAccounts --location uksouth

# Subscription: BlobCreated only, filtered to the intake- containers and the
# allowlisted extensions. Repeat --advanced-filter per extension as needed.
az eventgrid system-topic event-subscription create \
  --resource-group rg-ig-control-tower \
  --system-topic-name ig-storage-topic \
  --name intake-to-parser \
  --endpoint-type azurefunction \
  --endpoint /subscriptions/<sub>/resourceGroups/rg-ig-control-tower/providers/Microsoft.Web/sites/document-parser-fn/functions/documentParser \
  --included-event-types Microsoft.Storage.BlobCreated \
  --subject-begins-with "/blobServices/default/containers/intake-"
```

Extension allowlist is also enforced in code (`ALLOWED_EXTENSIONS`), so the
Event Grid filter is defence-in-depth, not the only gate.

### Containers (one pair per client)

```bash
az storage container create --name intake-downing-llp    --account-name <acct>
az storage container create --name processed-downing-llp --account-name <acct>
```

### FCA — blob access logging (zero code)

Enable diagnostic settings on the storage account → Log Analytics workspace.
This gives the immutable file-access log FCA requires. No code change.

---

## Smoke tests after deploy

These are Groups 6-7 of the 38-test suite (see `../../WORK_PLAN.md`):

- Upload a `.vtt` to `intake-{slug}/`; confirm `processed-{slug}/evidence/*_fragments.jsonl` appears within seconds.
- Confirm the fragments match what Path A produces for the same file (schema parity).
- Run the pipeline; confirm `_download_azure_fragments` pulls the JSONL into `Meeting-Notes/`.
- Confirm the FCA traceability chain (fragment_id lineage) is intact end to end.
