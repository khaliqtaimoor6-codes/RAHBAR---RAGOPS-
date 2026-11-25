# RAGOps layer (Assignment 03): what is built, where, and how to run it

This file tracks Assignment 03 work in this repository. It covers **Part A** (data
management), **Part D** (observability and traceability) and the **data side of Part F**
(PVCs, ingestion Job/CronJob, traces on a volume). Parts B, C, E, the eval Job and the
controlled release (F2 eval, F3) are in [HANDOFF-TEAMMATE.md](HANDOFF-TEAMMATE.md).

Status legend: ✅ code + unit tests done · 🟡 code done, needs a cluster run for results ·
⬜ not started

## Map (Figure 3 of the paper → this repo)

| Figure 3 stage | What RAHBAR does | File | Status |
| --- | --- | --- | --- |
| Ingest | Public corpus fetched into the lake's `mirror/`; new batches copied into `inbox/` | `corpus/fetch.py`, `scripts/lake.sh upload` | ✅ |
| Verify | 4 checks per document (quality, completeness, recency, uniqueness) + injection flag; failures to `quarantine/<run>/` with a reason file; one report per run | `indexer/pipeline/verify.py`, `ingest.py` | ✅ 🟡 |
| Update data lake | `current/`, `archive/<family>/<version>/`, `deleted/`, registry, extracted-text cache | `indexer/pipeline/lake.py` | ✅ |
| Update retrieval sources | Reconcile Chroma with the lake: embed only new/changed chunks, metadata-only archive/restore, delete by doc_id | `indexer/pipeline/reconcile.py` | ✅ 🟡 |
| Offline testing | Golden set, 3-level suite, gate | teammate (Part B/C) | ⬜ |
| Live testing / monitoring | One trace per query, metrics, summary script, trace tool | `api/app/services/trace.py`, `api/app/tools/` | ✅ 🟡 |
| Check coverage | Live-query coverage vs golden set | teammate (Part E) | ⬜ |

## Part A: data management

### A1. Verification stage (`indexer/pipeline/verify.py`)

Runs after extraction and before chunking, for every file that is new or changed.

| Check | Fails when | Threshold (ConfigMap) |
| --- | --- | --- |
| quality | extraction raised (corrupt/truncated PDF); fewer than `VERIFY_MIN_WORDS` words (empty); share of ordinary characters `< VERIFY_MIN_CLEAN_CHARS` or >1% U+FFFD (garbled); share of word-like tokens `< VERIFY_MIN_WORDLIKE` | 40 / 0.85 / 0.55 |
| completeness | `source`, `title` or `doc_version` missing, or 0 pages; truncated: PDF without `%%EOF`, page count differs from metadata, or text ending mid-sentence | — |
| recency | a newer `doc_version` of the same `family` is in the lake or in the same batch | — |
| uniqueness | same file hash or same normalised-text hash as another document (exact); document-fingerprint cosine ≥ `NEAR_DUP_THRESHOLD` with a document of another family (near) | 0.985 |
| injection (advisory) | instruction-like text ("ignore all previous instructions", ...). Never fails a document: it is indexed with `injection_suspect=true` so the query-time rail (D4) can be tested | — |

Decision: quality / completeness / uniqueness failure → **quarantine** (not indexed).
Recency failure alone → **archive** (indexed with `superseded=true`, excluded from
retrieval by metadata, restorable). Otherwise → **index**; an older version it supersedes
is archived.

Metadata comes from `corpus/sources.yaml` (via `_index.json`) for the public corpus, from
front matter for `.md`/`.txt`, and from a `<file>.meta.json` sidecar for PDFs/HTML.
`family` groups the versions of one document (the 2023 and 2026 academic rules).

Output per run: `/data/lake/reports/verify-<run_id>.json` and a table in the Job log.

### A2. Incremental update (`indexer/pipeline/reconcile.py`)

The lake registry is the desired state; a Chroma collection is brought in line with it:

| Situation | What happens | Embedded |
| --- | --- | --- |
| unchanged corpus | nothing | **0** |
| document changed | its chunks deleted by `doc_id` and re-added; chunks whose text is identical keep their stored vector | only the changed chunks |
| document deleted (`_delete.txt`) | file to `deleted/<run>/`, chunks removed; report prints chunks per `doc_id` and `orphan_chunks` (must be 0) | 0 |
| newer version arrives | old version's file to `archive/`, its chunks re-labelled `superseded=true` | only the new document |
| rollback (`_restore.txt`) | archived version current again, the newer one archived; metadata only | **0** |

Every chunk carries `doc_id, family, title, doc_version, superseded, doc_sha, text_sha,
chunk_cfg, injection_suspect`. A run that changes anything stamps a new `index_id` on the
collection, which namespaces the API's semantic cache, so no stale answer is served.

### Batch B (`data/batch_b/`, made by `scripts/make_batch_b.py`)

12 synthetic documents written by us. Expected outcome:

| File | Planted problem | Expected |
| --- | --- | --- |
| b01 midterm exam notice | — | index |
| b02 library borrowing rules | — | index |
| b03 midterm notice COPY | exact duplicate of b01 (bytes) | quarantine: uniqueness |
| b04 library rules reformatted | exact duplicate of b02 (same text, re-wrapped) | quarantine: uniqueness |
| b05 lab policy revised draft | near-duplicate of b11 | quarantine: uniqueness |
| b06 final exam notice | truncated mid-sentence | quarantine: completeness |
| b07 scholarship policy (PDF) | corrupt, cut-off PDF | quarantine: quality |
| b08 sports facilities | missing title and doc_version | quarantine: completeness |
| b09 fee structure 2027-28 | newer version of the fee page (family `fee-structure-page`) | index; 2026-27 page archived |
| b10 attendance notice | injected instruction | index, flagged; dropped at query time (D4) |
| b11 computer lab policy | — | index |
| b12 transcript request procedure | — | index |

### Commands (Part A)

```bash
kubectl -n rahbar logs job/ingest -c ingest            # first run: verification table + counts
scripts/lake.sh ingest                                 # re-run on the unchanged corpus: 0 embedded
scripts/lake.sh upload data/batch_b && scripts/lake.sh ingest     # Batch B through A1 + A2
scripts/lake.sh delete b12-transcript-request-procedure && scripts/lake.sh ingest  # no orphans
scripts/lake.sh restore fee-structure-page && scripts/lake.sh ingest              # rollback
scripts/lake.sh pull                                   # reports -> eval/results/ingest/
```

## Part D: observability and traceability

| Item | What | Where |
| --- | --- | --- |
| D1 trace record | One JSON line per query: trace id, timestamp, query, rewritten query (none: RAHBAR does not rewrite; lexical terms listed under filters), embedding model + Ollama digest, collection name + `index_id` + `indexed_at`, retrieved chunk ids with doc ids, versions and scores, filters, dense order vs RRF-reranked order, the exact context sent, prompt hash + template version, model and parameters, response, citations, guardrail actions, latency per stage, cache hit/miss/skip | `api/app/services/answer.py`, `trace.py` |
| D2 trace tool | Rebuilds the exact prompt for a trace id and checks it against the recorded SHA-256 | `python -m app.tools.trace_show <id>` |
| D3 metrics | `/metrics`: `rahbar_top1_similarity`, `rahbar_abstention_rate`, `rahbar_cache_hit_ratio`, `rahbar_stage_seconds{stage}`, `rahbar_injection_flagged_total`; the script summarises the trace log over a window | `api/app/routes/metrics.py`, `python -m app.tools.trace_summary --since 1h` |
| D4 guardrail logging | Retrieval rail drops (or flags) instruction-like chunks and chunks flagged at ingest; the question is scanned too; every action is a `guardrails` entry in the trace | `api/app/services/rails.py` |
| D5 root cause | needs a wrong/abstained answer from Part B | teammate, with `trace_show` |

```bash
kubectl -n rahbar logs deploy/api | grep rahbar.trace | tail -1          # F4: traces on stdout
kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show <trace_id>
kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_summary --since 60m
kubectl -n rahbar port-forward svc/api 8000:8000 & curl -s localhost:8000/metrics | grep rahbar_
```

Every `/api/ask` response now carries `trace_id`, so the eval suite can link each answer
to its trace.

## Part F (data side)

| Item | Object | File |
| --- | --- | --- |
| F1 data lake, quarantine, archive survive restarts | PVC `rahbar-lake` | `k8s/base/pvc.yaml` |
| F1 vector store | StatefulSet `chroma` with `volumeClaimTemplates` (from A2) | `k8s/base/chroma-statefulset.yaml` |
| F2 ingestion with verification | Job `ingest`, CronJob `ingest` (nightly, `concurrencyPolicy: Forbid`, plus a lake lock) | `k8s/base/ingest-job.yaml`, `ingest-cronjob.yaml` |
| F2 only one writer | api code never writes; NetworkPolicy admits only `app=api` / `app=indexer` to chroma; lake-shell pod has no network | `k8s/base/networkpolicy.yaml` |
| F4 traces on stdout and a volume | PVC `rahbar-traces` mounted at `/traces` in the api | `k8s/base/api-deployment.yaml` |
| F5 resources | ingest Job / api / chroma requests and limits | 🟡 re-measure with `kubectl top` on our cluster |

## Results

🟡 Not run on our cluster yet. After the first full run, copy the reports in with
`scripts/lake.sh pull` and put the numbers here and in the report:

- first ingestion: documents indexed / archived / quarantined, chunks embedded
- second ingestion on the unchanged corpus: `chunks_embedded = 0`
- Batch B verification table
- delete: chunks for the doc_id before/after, `orphan_chunks = 0`
- restore: `superseded` flipped, 0 chunks embedded; a trace afterwards
- `kubectl top` numbers for F5

## Tests

`make test` (or `cd indexer && pytest`, `cd api && pytest`): 28 indexer tests (8 new for
Part A) and 46 api tests (6 new for Part D), no network, no model.
