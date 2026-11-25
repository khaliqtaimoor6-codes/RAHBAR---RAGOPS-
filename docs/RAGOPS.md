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
| F5 resources | ingest Job / api / chroma requests and limits | measured, see Results |

## Results (our minikube cluster, 25 Nov 2026)

Raw logs: `docs/evidence/a3/`. Machine-readable reports: `eval/results/ingest/`
(`verify-<run>.json`, `ingest-<run>.json`). Trace sample: `traces/cluster/`.

### A: ingestion runs

| Run | What | Verified | Indexed / archived / quarantined | Chunks embedded | Other | Time |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | first run, public corpus (9 docs) | 9 | 8 / 1 / 0 | **1008** | 2023 rules archived by recency (2026 handbook is newer, same family); 24 pages OCR'd | 370 s |
| 2 | same corpus again | 0 (9 unchanged) | — | **0** | `index_id` unchanged, so the cache stays valid | 3.3 s |
| 3 | Batch B | 11 (+10 unchanged) | 6 / 0 / 5, fee page relabelled `superseded` | **26** | 9 chunks metadata-only | — |
| 3b | b03 re-sent after the fix below | 1 | 0 / 0 / 1 | 0 | — | 3.5 s |
| 4 | delete `b12-transcript-request-procedure` | — | — | 0 | chunks for b12: **4 → 0**, `orphan_chunks = 0` | 4.0 s |
| 5 | restore `fee-structure-page` (rollback) | — | — | **0** | 13 chunks relabelled; 2027-28 archived, 2026-27 current | 2.7 s |
| C | candidate collection `rahbar-cand-cs300` (`--reconcile-only`, CHUNK_SIZE 300) | — | 14 docs | 834 | live `rahbar` untouched; no re-download, no re-OCR | 34 s |

### Batch B verification (A1)

| Doc | quality | complete | recency | unique | Action | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| b01 midterm notice | PASS | PASS | PASS | PASS | index | |
| b02 library rules | PASS | PASS | PASS | PASS | index | |
| b03 midterm COPY | SKIP | SKIP | SKIP | **FAIL** | quarantine | exact duplicate of b01 (same file hash, different file name) |
| b04 library reformatted | PASS | PASS | PASS | **FAIL** | quarantine | exact duplicate of b02 (same text) |
| b05 lab draft | PASS | PASS | PASS | PASS | index | arrived first (name order) |
| b06 final notice | PASS | **FAIL** | PASS | PASS | quarantine | text ends mid-sentence |
| b07 scholarship PDF | **FAIL** | SKIP | PASS | PASS | quarantine | extraction failed: `PdfminerException: Unexpected EOF` |
| b08 sports | PASS | **FAIL** | PASS | PASS | quarantine | missing source, title, doc_version |
| b09 fee 2027-28 | PASS | PASS | PASS | PASS | index | supersedes `fee-structure-page` (archived) |
| b10 attendance | PASS | PASS | PASS | PASS | index + FLAG | injection: "Ignore all previous instructions" |
| b11 lab policy | PASS | PASS | PASS | **FAIL** | quarantine | near-duplicate of b05, cosine **0.9997** |
| b12 transcript | PASS | PASS | PASS | PASS | index | |

Count by check: uniqueness 3, completeness 2, quality 1 (+1 newer version handled by
recency, +1 injection flagged). Every planted problem was caught.

**Found and fixed on the cluster.** In the first Batch B run, b03 (a byte copy of b01,
front matter included, so it carried b01's `doc_id`) was reported as "unchanged" and
silently dropped instead of being reported as a duplicate. The loop now treats "same
bytes, same doc_id, different file name" as an exact duplicate (`ingest.py`, with a
test); run 3b shows it quarantined.

**Near-duplicates: first arrival wins.** Files are processed in name order, so the draft
(b05) was accepted and the original (b11) quarantined. Detection is symmetric; which copy
survives is an ordering policy. A better policy would prefer the document with the newer
`doc_version` or the longer text.

**Why NEAR_DUP_THRESHOLD = 0.985.** Document-fingerprint cosines between genuinely
different documents in our corpus: highest 0.9606 (Annual Report 2019-20 vs 2023-24),
then 0.9124 (b06 vs b01, same template), all others ≤ 0.862. The planted near-duplicate
scored 0.9997. 0.985 sits in the gap with margin on both sides.

### D: traces (first queries, before the Groq key was set)

- `trace_show` on the attendance question (`docs/evidence/a3/D2-trace-show-injection.txt`):
  prompt hash recorded = rebuilt (**MATCH**); embedding `nomic-embed-text@0a109f422b47`;
  collection `rahbar@20ade7ea03b5`; filter `{"superseded": false}`.
- D4: the 3 chunks of b10 were dropped by the retrieval rail (one matched the pattern,
  two because the whole document was flagged at ingest; doc-level is the stricter
  choice, and drops the document's harmless clauses too).
- `trace_summary` (`D3-trace-summary.txt`): embed p95 18 s on the very first query (Ollama
  loading the model from cold), ~67 ms after that; retrieve p50 25 ms; rails < 1 ms.
- Answers were the safe fallback (no LLM key yet); re-run once the key is set.

### F5: resources (`kubectl top`, idle, after ingestion)

| Pod | CPU | Memory | Requests / limits set |
| --- | --- | --- | --- |
| api (×2) | 6–8m | 69–71 Mi | 50m / 128Mi → 500m / 256Mi |
| chroma-0 | 3–24m | 106–107 Mi (1,034 + 834 chunks in two collections) | 25m / 96Mi → 500m / 384Mi |
| redis | 24m | 9 Mi | (from A2) |
| ingest Job | — | — | 250m / 256Mi → 1500m / 768Mi |

The candidate rebuild finished in 34 s, faster than metrics-server's sampling interval,
so no Job sample was caught. The Job now logs its own peak RSS (`peak_rss_mb` in the
`ingestion finished` line); the A2 measurement of the OCR peak was 186 Mi / 1411m.
Chroma's request (96Mi) is now below its measured 107 Mi: raise to 128Mi.

## Tests

`make test` (or `cd indexer && pytest`, `cd api && pytest`): 28 indexer tests (8 new for
Part A) and 46 api tests (6 new for Part D), no network, no model.
