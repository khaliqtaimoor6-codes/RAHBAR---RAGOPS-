# Report draft: Parts A, D, F (data side) — Taimoor

Draft text for the Assignment 03 report (Part G). Every number comes from our minikube
runs on 25 Nov 2026; the raw output is in `docs/evidence/a3/` and `eval/results/ingest/`.
Ali's parts (B, C, E, F2-eval, F3, D5) slot into the same sections.

## G1. Figure 3 stages → RAHBAR (rows for A and D)

| Stage | What our pipeline does | File | What is missing |
| --- | --- | --- | --- |
| Ingest | `fetch-corpus` init container mirrors the 9 public documents into the lake PVC and checks each SHA-256 against `corpus/MANIFEST.md`; operators drop new batches into `inbox/` | `corpus/fetch.py`, `scripts/lake.sh upload` | no push-based source (webhook / crawler); batches are copied by hand |
| Verify | quality, completeness, recency, uniqueness per document, plus an advisory injection flag; failures to `quarantine/<run>/` with a reason file; one JSON report per run | `indexer/pipeline/verify.py`, `ingest.py` | no check of factual consistency between documents |
| Update data lake | `current/`, `archive/<family>/<version>/`, `deleted/<run>/`, registry, cached extracted text | `indexer/pipeline/lake.py` | no retention policy for `deleted/` and `quarantine/` |
| Update retrieval sources | reconcile Chroma with the registry: embed only new/changed chunks, metadata-only archive/restore, delete by `doc_id`, new `index_id` invalidates the cache | `indexer/pipeline/reconcile.py` | updates are not atomic across documents (a crash mid-run leaves a partly updated collection until the next run) |
| Live testing (monitoring part) | one trace per query, `/metrics`, trace summary over a window, trace tool | `api/app/services/trace.py`, `api/app/tools/` | no alerting; metrics are pulled by hand |

## G2. Paper Table 2 qualities (rows for our parts)

| Quality | What we measure | Threshold | Evidence |
| --- | --- | --- | --- |
| Adaptability | chunks embedded when re-running on an unchanged corpus; time to build a candidate collection | 0 chunks | 0 chunks, 3.3 s; candidates in 34 s (cs300) and 55 s (cs100) without re-download or re-OCR |
| Observability | fields per trace record; stages with their own latency | all D1 fields | 18 top-level fields; embed / cache / retrieve / rails / generate / total in every trace |
| Traceability | rebuilt prompt hash = recorded hash | 100 % | MATCH on every trace checked (`D2-trace-show-*.txt`) |
| Monitorability | top-1 similarity, abstention rate, cache hit rate, p95 per stage, injection count over a window | — | `D3-trace-summary.txt` (15 traces: abstention 0.47, cache hit 0.27, 6 injected chunks dropped) |
| Reliability | orphan chunks after delete; data after a vector-store restart | 0; unchanged | 0 orphans in every run; after `chroma-0` restarted all 3 collections were intact (rahbar 1,030 chunks, same `index_id`) |

## G3. Results

### A1 verification of Batch B

| Doc | quality | complete | recency | unique | Action | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| b01 midterm notice | PASS | PASS | PASS | PASS | index | |
| b02 library rules | PASS | PASS | PASS | PASS | index | |
| b03 midterm COPY | SKIP | SKIP | SKIP | FAIL | quarantine | exact duplicate of b01 (same file hash) |
| b04 library reformatted | PASS | PASS | PASS | FAIL | quarantine | exact duplicate of b02 (same text) |
| b05 lab draft | PASS | PASS | PASS | PASS | index | arrived first |
| b06 final notice | PASS | FAIL | PASS | PASS | quarantine | ends mid-sentence |
| b07 scholarship PDF | FAIL | SKIP | PASS | PASS | quarantine | `PdfminerException: Unexpected EOF` |
| b08 sports | PASS | FAIL | PASS | PASS | quarantine | missing source, title, doc_version |
| b09 fee 2027-28 | PASS | PASS | PASS | PASS | index | supersedes the 2026-27 fee page |
| b10 attendance | PASS | PASS | PASS | PASS | index + flag | "Ignore all previous instructions" |
| b11 lab policy | PASS | PASS | PASS | FAIL | quarantine | near-duplicate of b05, cosine 0.9997 |
| b12 transcript | PASS | PASS | PASS | PASS | index | |

Near-duplicate threshold 0.985: the most similar pair of genuinely different documents is
Annual Report 2019-20 vs 2023-24 at 0.9606; the planted near-duplicate scored 0.9997.

### A2 incremental update

| Run | Chunks embedded | Other |
| --- | --- | --- |
| first (9 docs, 24 OCR pages) | 1,008 | 8 indexed, 1 archived (2023 rules, by recency) — 370 s |
| unchanged corpus | **0** | 9 unchanged, `index_id` kept — 3.3 s |
| Batch B | 26 | 6 indexed, 5 quarantined (+ b03 after the fix), fee page relabelled (9 chunks) |
| delete b12 | 0 | b12 chunks 4 → 0, orphans 0 |
| restore fee page | **0** | 13 chunks relabelled — 2.7 s |

### D sample answers (Groq `openai/gpt-oss-20b`, temperature 0.2)

CGPA for warning → 2.00 (5.4); withdrawal deadline → last day of the makeup week (2026);
"is attendance optional?" → No (the injected b10 chunks were dropped before the model);
"what did the 2023 rules say?" → last day of classes (archived version, retrieved on
request); hostel → declined; capital of France → abstained at the relevance floor.

### F5 resources (from our measurements)

| Workload | Measured | requests → limits |
| --- | --- | --- |
| api | 6–8m CPU, 69–71 Mi idle | 50m / 128Mi → 500m / 256Mi |
| chroma | 2–24m, 159 Mi with 3 collections | 25m / 192Mi → 500m / 384Mi |
| ingest Job | peak RSS 111 Mi (1,262 chunks embedded), 85 Mi (no-op); OCR peak 186 Mi (A2) | 250m / 256Mi → 1500m / 512Mi |

### Two defects found on the cluster (worth a line in the report)

1. A byte-for-byte copy under another file name carried the original's `doc_id` in its
   front matter and was treated as "unchanged" instead of a duplicate. Fixed in
   `ingest.py`, with a test; the re-run quarantined it.
2. `trace_show` crashed on traces of cache hits (no `rank` in the cached retrieval list).
   Fixed in the tool and in the trace writer, with a test.

## G4. Short answers (our parts)

**(a)** Uniqueness caught the most problems in Batch B (3 of 7: one byte copy, one
re-wrapped text copy, one near-duplicate); completeness caught 2, quality 1, and recency
handled the newer fee page. The problem we did not catch at first was the byte copy that
reused the original's `doc_id` (fixed, see above). What we still would not catch: a
document that is new, well-formed and unique but *wrong* or contradicts another policy
(no check compares facts across documents; an NLI or LLM contradiction check over
documents of the same topic would), and which copy of a near-duplicate survives depends
on arrival order (preferring the newer `doc_version` would fix that).

**(c)** We archive, never delete, superseded versions: their chunks stay in the index with
`superseded=true` and the retriever filters them out unless a question asks for an older
edition. Deleting them would break (1) rollback (`_restore.txt` relabels 13 chunks in
2.7 s with 0 re-embedding; after a delete it means re-fetching and re-embedding),
(2) questions about an older edition ("what did the 2023 rules say?" was answered from the
archive), and (3) audits of old traces, whose chunk ids would point at nothing.
Operator deletions move the file to `deleted/<run>/` so even those are recoverable.

**(f)** Kubernetes objects and their RAGOps duties:
- Job `ingest` (+ CronJob `ingest`, `concurrencyPolicy: Forbid`, plus a lock file in the
  lake): the only writer to the vector store. The NetworkPolicy
  `chroma-from-api-and-indexer` admits only `app=api` (read-only code) and `app=indexer`.
- PVC `rahbar-lake`: data lake, quarantine, archive, reports — survives pod restarts.
- StatefulSet `chroma` with its `volumeClaimTemplate`: the retrieval sources.
- ConfigMap `rahbar-config`: verification thresholds, `NEAR_DUP_THRESHOLD`,
  `INJECTION_ACTION`, the embedding pin `EMBED_MODEL` (Ali: gate thresholds).
- PVC `rahbar-traces` + stdout: traceability (`kubectl logs` and the report scripts).
- Deployment `api` readiness probe: refuses traffic if the index was built with another
  embedding model.
- Secret `rahbar-secret`: the LLM key, created from the command line, never in a file.

## Contribution (Taimoor)

Part A (verification stage, data lake, incremental update, Batch B), Part D1–D4 (trace
record, trace tool, metrics and summary, retrieval injection rail), Part F1/F2-ingestion/
F4/F5 (PVCs, ingestion Job and CronJob, traces on stdout and a volume, measured resources),
the cluster runs and evidence for those parts, and the repository setup.
