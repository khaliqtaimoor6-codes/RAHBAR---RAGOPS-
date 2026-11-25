# Demo and screenshot checklist (Parts A, D, F)

Every command is PowerShell, run from the repo root. Screenshots must show the command and
its full output in your own terminal, uncropped, labelled with the part (e.g. "A1").
Ali's checklist for B, C, E, F2-eval and F3 goes in the same file.

## Before the demo (once, ~5 min)

```powershell
minikube start
```
```powershell
kubectl -n rahbar get pods
```
All pods `Running` and `1/1` (the api pods need chroma first; give them a minute).
Ollama must be running (tray icon) with `nomic-embed-text` pulled.

```powershell
kubectl -n rahbar port-forward svc/api 8000:8000
```
Leave that window open; use a second window for everything below.

## Screenshots

Already taken from our cluster and in `docs/screenshots/` (and in the report appendix).
To retake them all, keep your hands off the keyboard for ~3 minutes and run:
```powershell
.\scripts\capture_screenshots.ps1
```
Each shot is a real PowerShell window running the command below, captured as it is.
Manual commands, if you prefer to take them yourself:


| Label | Command | Shows |
| --- | --- | --- |
| A1 | `.\scripts\lake.ps1 report 20261125T1846` | Batch B verification table: pass/fail per check with reasons |
| A1b | `.\scripts\lake.ps1 report 20261125T184827` | b03 byte-copy quarantined after the fix |
| A2 | `.\scripts\lake.ps1 ingest` (on the unchanged corpus) | `chunks_embedded 0`, `docs_unchanged`, `orphan_chunks 0` |
| A2 delete | `.\scripts\lake.ps1 delete c02-laptop-loan-scheme` then `.\scripts\lake.ps1 ingest` | chunks for that doc_id gone, `orphan_chunks 0` |
| A2 rollback | `.\scripts\lake.ps1 restore b09-fee-structure-2027-28` then `.\scripts\lake.ps1 ingest` | 2027-28 current again, 2026-27 archived, `chunks_embedded 0` |
| D1 | `kubectl -n rahbar logs deploy/api \| Select-String rahbar.trace \| Select-Object -Last 1` | one full trace record |
| D2 | `kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show <trace_id>` | context, prompt, `MATCH` |
| D3 | `kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_summary --since 2h` | metrics over a window |
| D3 live | `curl.exe -s localhost:8000/metrics \| Select-String "rahbar_(top1\|abstention\|cache_hit\|stage\|injection)"` | the metrics endpoint via port-forward (F4) |
| F | `kubectl -n rahbar get all,pvc,configmap,cronjob,job` | every object |
| F logs | `kubectl -n rahbar logs job/ingest -c ingest \| Select-Object -Last 30` | a completed ingestion Job |

To get a fresh `<trace_id>`, ask a question:
```powershell
curl.exe -s -X POST localhost:8000/api/ask -H "Content-Type: application/json" -d '{\"question\": \"What CGPA avoids academic warning?\"}'
```
The reply ends with `"trace_id": "..."`.

## Live in the demo: "ingest documents you have not seen"

1. Put the examiner's files in a new folder, e.g. `data\demo_live\`.
2. ```powershell
   .\scripts\lake.ps1 upload data\demo_live
   ```
3. ```powershell
   .\scripts\lake.ps1 ingest
   ```
   The verification table prints, then the incremental update with chunks per doc_id.

What to expect:
- **PDFs without a metadata file** are fine: the Job takes the version from the PDF's
  date and the title from its properties or first line (`derived from the file` in the
  completeness reason). Rehearsed with `data\demo_batch_c` (2 PDFs indexed).
- **An HTML page has no date**, so it is quarantined for missing `doc_version` (c03 in
  the rehearsal). That is the completeness check working; to index it anyway, add a
  sidecar `page.html.meta.json` with `{"title": "...", "doc_version": "2026", "source": "..."}`.
- **Markdown** must carry front matter (`title`, `doc_version`, `source`), like Batch B.
- A copy of something already indexed is quarantined as a duplicate.

Then ask a question about the new document and open its trace (D2).

## Questions you may get (short answers)

- *Why is the ingestion a Job and not part of the api?* It is the only writer to Chroma;
  the api only reads. Re-indexing never needs a redeploy, and two writers never overlap
  (CronJob `concurrencyPolicy: Forbid` + a lock file in the lake).
- *What happens on a re-run with nothing new?* Every file's hash matches the registry:
  0 chunks embedded, same `index_id`, ~4 s.
- *How do you know which prompt produced an answer?* The trace stores the exact context
  and a SHA-256 of the messages; `trace_show` rebuilds the prompt and compares hashes.
- *Why archive instead of delete?* Rollback is a metadata flip (0 re-embedding), older
  editions stay answerable on request, and old traces stay auditable.
- *What did you find on the cluster?* A byte copy reusing the original's doc_id slipped
  through as "unchanged"; the trace tool crashed on cache-hit traces. Both fixed with tests.
