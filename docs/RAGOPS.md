# RAGOps layer (Assignment 03): what is built, where, and how to run it

This file tracks Assignment 03 work in this repository: **Part A** (data management),
**Part B** (offline testing at three levels) with the **eval Job**, **Part D**
(observability and traceability, including D5) and the **data side of Part F**. Parts C, E,
the F2 gate and F3 are documented below.

Status legend: ✅ code + unit tests done · 🟡 code done, needs a cluster run for results ·
⬜ not started

## Map (Figure 3 of the paper → this repo)

| Figure 3 stage | What RAHBAR does | File | Status |
| --- | --- | --- | --- |
| Ingest | Public corpus fetched into the lake's `mirror/`; new batches copied into `inbox/` | `corpus/fetch.py`, `scripts/lake.sh upload` | ✅ |
| Verify | 4 checks per document (quality, completeness, recency, uniqueness) + injection flag; failures to `quarantine/<run>/` with a reason file; one report per run | `indexer/pipeline/verify.py`, `ingest.py` | ✅ 🟡 |
| Update data lake | `current/`, `archive/<family>/<version>/`, `deleted/`, registry, extracted-text cache | `indexer/pipeline/lake.py` | ✅ |
| Update retrieval sources | Reconcile Chroma with the lake: embed only new/changed chunks, metadata-only archive/restore, delete by doc_id | `indexer/pipeline/reconcile.py` | ✅ 🟡 |
| Offline testing | Golden set (34), three-level suite, two seeded runs, as a Job | `eval/ragops_suite.py`, `k8s/eval-job.yaml` | ✅ (gate: Part C) |
| Live testing / monitoring | One trace per query, metrics, summary script, trace tool | `api/app/services/trace.py`, `api/app/tools/` | ✅ 🟡 |
| Check coverage | Live-query coverage vs golden set | `eval/live_queries.py`, `eval/coverage.py`, `eval/golden-e4.jsonl` | 🟡 |

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

### Metadata for files dropped without any

Markdown/text must declare front matter. A PDF or HTML page without a
`<file>.meta.json` sidecar gets metadata derived from the file itself: `source` = its inbox
path, `doc_version` from the PDF's ModDate/CreationDate, `title` from the PDF Title or
the HTML `<title>`, else the first line of 2-15 words. Derived keys are named in the
completeness reason. Anything that cannot be derived (an HTML page has no date) stays
missing and fails completeness. Rehearsed with `data/demo_batch_c/`
(`scripts/make_demo_batch.py`): 2 plain PDFs indexed, 1 HTML page quarantined for
`doc_version` (`docs/evidence/a3/A-ingest-demo-batch-c-rehearsal.txt`).

`scripts/lake.sh report [run]` (or `.\scripts\lake.ps1 report [run]`) re-prints any saved
verification report as a table; Jobs and their logs are garbage-collected, the reports on
the lake volume are not. The demo steps are in [DEMO-CHECKLIST.md](DEMO-CHECKLIST.md).

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

## Part B: offline testing at three levels

**Golden set** `eval/golden.jsonl` (built by `eval/build_golden.py`): 34 questions; 28
answerable with ground-truth `doc_id` and page(s), 6 unanswerable, 16 hard (version,
exact-term, injection, paraphrase, multi-chunk, Batch B/demo documents). 21 are the
group's hand-written Assignment 02 questions (`human`), 13 are new (`synthetic`,
`reviewed: false` until a member checks them: see `eval/REVIEW-SYNTHETIC.md`). Pages come
from an export of the live index (`eval/index_sections.json`); g11 and g12, whose headings
are not chunk labels, use the pages documented in PIPELINE.md.

**Suite** `eval/ragops_suite.py`, one command, as a Job:

```bash
kubectl -n rahbar delete job eval --ignore-not-found; kubectl apply -f k8s/eval-job.yaml
kubectl -n rahbar logs -f job/eval        # summary table at the end
scripts/lake.sh pull                      # -> eval/results/suite/ragops-<ts>.json/.md
```

A chunk is relevant when its `doc_id` is a ground-truth document and its page is a
ground-truth page. The component level calls `POST /api/retrieve` (retrieval only, no LLM);
the end-to-end level calls `/api/ask` with `X-RAHBAR-Cache: bypass`, and the judge reads
each answer's exact context from its trace. Both runs use seed 1234 (typos, `LLM_SEED`,
judge).

### Results (run `20261126T104001Z`, collection `rahbar@f4c2ff9a3277`, 18 min)

| Level | Metric | Run 1 | Run 2 | Diff |
| --- | --- | --- | --- | --- |
| module | paraphrase mean cosine (15 pairs) | 0.7864 | 0.7864 | 0 |
| module | unrelated mean cosine (15 pairs) | 0.4600 | 0.4600 | 0 |
| module | gap | 0.3264 | 0.3264 | 0 |
| module | ms per chunk (one request / batched) | 41.9 / 28.1 | 48.5 / — | +6.6 |
| module | determinism: max abs diff, same text twice | 0.0 | 0.0 | 0 |
| component | recall@3 / recall@5 | 0.911 / 0.964 | 0.911 / 0.964 | 0 |
| component | MRR / nDCG@5 | 0.830 / 0.838 | 0.830 / 0.838 | 0 |
| component | with typos: recall@5 / MRR | 0.929 / 0.839 | same | 0 |
| end-to-end | faithfulness (judged answers) | 1.0 (25/28) | 1.0 (24/26) | 0 |
| end-to-end | abstention correct on unanswerable | 0.833 | 0.833 | 0 |
| end-to-end | false abstention on answerable | 0.036 | 0.107 | +0.071 |
| end-to-end | citations in retrieved / to a ground-truth doc | 1.0 / 0.870 | 1.0 / 0.873 | +0.003 |
| end-to-end | expected string in answer | 0.857 | 0.714 | −0.143 |
| end-to-end | latency p50 / p95 (ms) | 8,191 / 13,681 | 8,934 / 13,662 | |

Faithfulness and the expected-string rate are from the re-judged file
(`ragops-20261126T104001Z-rejudged-1.json`, same answers, fixed judge and matcher).

**Reading the numbers**
- Typos (one swapped letter pair in about a third of the longer words, 28 questions) cost 3.6 points of recall@5 and 2.4 of nDCG@5; MRR is unchanged within 0.01.
- The only full retrieval miss is **g11** (Lahore graduates table): the extraction loss
  documented in Assignment 02. In run 2 the model answered "53", a wrong number from the
  garbled table, which faithfulness does not catch (the number *is* in the context).
- **Stochasticity**: embeddings and retrieval are bit-identical across the two runs
  (determinism 0.0, same ranks). All variation is in generation: with `LLM_SEED`, the
  temperature 0.2 model still returned invalid JSON 1 time in run 1 and 3 times in run 2;
  the safe fallback turned those into abstentions (false abstention 0.036 → 0.107) and
  their expected strings into misses. Latency varies with Groq's load and rate limiting
  (p50 ~8–9 s includes the pacing waits of the free tier).
- Latency p50 of ~8 s is dominated by the hosted model; retrieval itself is ~25–70 ms.

**Found and fixed while running it on the cluster**: the judge model first returned 404 and
crashed the run; Groq then rejected 5 judge replies as invalid JSON (faithfulness was over
23 of 28); 3 more came back unparsable because gpt-oss spends part of max_tokens on
reasoning; and the expected-string match failed on "six" vs "6" and "100 %" vs "100%".
Each is its own commit with the evidence.

**Still by hand (both members):** review ≥ 8 synthetic questions and label ≥ 8 judge
verdicts, then `eval/judge_agreement.py` gives the agreement (`eval/REVIEW-SYNTHETIC.md`).

### D5: root cause from the trace only (a02, answered though labelled unanswerable)

Trace `21e2196d` ("What are the university bus routes and how much is the transport fee?"):
1. Retrieved 4 annual-report chunks titled "Islamabad Campus"/"Karachi Campus" from the
   transport pages (2023-24 p.78, 2019-20 p.32), describing mini-buses and pick-and-drop.
2. Top-1 similarity 0.6685, 0.0085 above `RELEVANCE_FLOOR` 0.66, so the model was called.
3. The answer and both citations match those chunks; the prompt hash matches the trace.
4. Cause: the **ground truth is wrong**, not the pipeline. The corpus does cover the bus
   service; only the fee is missing. Assignment 02 assumed the annual reports say nothing
   about transport.
5. Fix: keep golden.yaml unchanged (it is only extended), record a02 as partially
   answerable, and add a fee-only abstain question in Part E.

## Part D: observability and traceability

| Item | What | Where |
| --- | --- | --- |
| D1 trace record | One JSON line per query: trace id, timestamp, query, rewritten query (none: RAHBAR does not rewrite; lexical terms listed under filters), embedding model + Ollama digest, collection name + `index_id` + `indexed_at`, retrieved chunk ids with doc ids, versions and scores, filters, dense order vs RRF-reranked order, the exact context sent, prompt hash + template version, model and parameters, response, citations, guardrail actions, latency per stage, cache hit/miss/skip | `api/app/services/answer.py`, `trace.py` |
| D2 trace tool | Rebuilds the exact prompt for a trace id and checks it against the recorded SHA-256 | `python -m app.tools.trace_show <id>` |
| D3 metrics | `/metrics`: `rahbar_top1_similarity`, `rahbar_abstention_rate`, `rahbar_cache_hit_ratio`, `rahbar_stage_seconds{stage}`, `rahbar_injection_flagged_total`; the script summarises the trace log over a window | `api/app/routes/metrics.py`, `python -m app.tools.trace_summary --since 1h` |
| D4 guardrail logging | Retrieval rail drops (or flags) instruction-like chunks and chunks flagged at ingest; the question is scanned too; every action is a `guardrails` entry in the trace | `api/app/services/rails.py` |
| D5 root cause | a02 from the Part B run, from its trace only | see Part B above |

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

## Part C: one pipeline change and the release gate

**C1.** One change: `TOP_K` 5 → 6 on the answer pipeline. The candidate reads the
baseline-equivalent collection `rahbar-cand-topk6` (1,032 chunks,
`nomic-embed-text|150|30|structure`, rebuilt from the lake after the restored PVC lost its
registry) with the same answer model as Part B (`openai/gpt-oss-20b`). The baseline remains
Part B's original two-run result `ragops-20261126T104001Z-rejudged-1.json`
(`rahbar@f4c2ff9a3277`, also 1,032 chunks). The deliberately bad candidates
`rahbar-cand-cs300` (CHUNK_SIZE 300, recall@5 0.6964) and `rahbar-cand-cs100` (CHUNK_SIZE
100, recall@5 0.6071) remain as gate-fail demos. The final candidate suite is
`20261128T115331Z` (TOP_K=6); it gates against the original Part B baseline, so the answer
model and embedding pin stay fixed and TOP_K is the only C1 change.

```bash
kubectl apply -f k8s/release/candidate-base-job.yaml   # full verify -> lake registry
kubectl -n rahbar wait --for=condition=complete job/ingest-cand-topk6-base --timeout=60m
# restore the superseded fee page before the final candidate reconcile
kubectl -n rahbar exec lake-shell -- sh -c 'echo fee-structure-page > /data/lake/inbox/_restore.txt'
kubectl apply -f k8s/release/candidate-topk6-job.yaml  # reconcile-only -> 1032 chunks
kubectl apply -f k8s/release/api-candidate-deployment.yaml   # gpt-oss-20b, TOP_K=6
kubectl -n rahbar rollout status deploy/api-candidate
kubectl delete job eval-candidate --ignore-not-found
kubectl apply -f k8s/release/eval-candidate-job.yaml
kubectl -n rahbar logs -f job/eval-candidate      # PASS/FAIL at the end
scripts/lake.sh pull                              # -> eval/results/suite/
```

The candidate suite `20261128T115331Z` gates against the original Part B baseline baked into
the eval image (`eval/baseline-a3.json`). Both report all three levels with the same answer
model and embedding pin.

**C2 / F2 gate.** `eval/gate.py` averages each metric over a result's runs, checks that
both results used the same question ids and embedding pin, then applies the rules in
`eval/gate-thresholds.yaml`: recall@5 may drop ≤ 2 points (paper §5.4), MRR/nDCG ≤ 3,
module paraphrase/gap ≤ 2, faithfulness ≥ 0.95 with ≤ 5 points of drop, abstention ≥ 0.83
(at most one of six must-abstain questions answered), false abstention ≤ 0.12 with ≤ 0.05
rise, citation validity ≥ 0.98, p95 ≤ 20 s and ≤ 125% of baseline. An unmeasured required
metric fails. The thresholds are mirrored in `k8s/base/gate-config.yaml`
(tested equal in `eval/tests/test_gate.py`) and mounted at `/etc/rahbar-gate/gate.yaml`; the
release Job exits 1 when the gate fails.

```bash
python eval/gate.py --candidate <candidate.json> \
  --baseline eval/results/suite/ragops-20261126T104001Z-rejudged-1.json
# re-run the gate on the newest saved result: no questions re-asked, no rebuild
kubectl -n rahbar delete job eval-gate --ignore-not-found
kubectl apply -f k8s/release/eval-gate-only-job.yaml
kubectl -n rahbar logs -f job/eval-gate
# flip a decision by editing only the ConfigMap, then restore it. With baseline recall@5
# = 0.9643 and candidate = 0.9643, max_drop -0.01 demands a 1-point gain and fails.
kubectl -n rahbar patch configmap rahbar-gate --type merge \
  -p '{"data":{"gate.yaml":"version: 1\nrules:\n  - id: component-recall5\n    level: component\n    metric: recall@5\n    max_drop: -0.01\n"}}'
kubectl -n rahbar delete job eval-gate --ignore-not-found
kubectl apply -f k8s/release/eval-gate-only-job.yaml
kubectl -n rahbar apply -f k8s/base/gate-config.yaml
```

Evidence: `eval/results/suite/*-gate.json/.md`, `docs/evidence/a3/C-gate-pass.txt` and
`docs/evidence/a3/F2-gate-config-change.txt` (pass → fail → pass without rebuilding the image).
`ragops-20261127T154916Z` is an earlier failed run: the fee page was archived by the fresh
verification (fixed with `_restore.txt`) and gpt-oss hit its 200000 TPD quota. After the quota
refreshed, `ragops-20261128T115331Z` passed against the original baseline; the interim qwen
runs remain in the results directory but are not used in C1/C2.

## Part E: live query log, coverage and drift

**E1.** 40 user-style queries in `eval/live_queries.jsonl` (28 in-domain, 12 off-topic)
are sent through `/api/ask` with the cache bypassed. Each call writes a trace in the api
pods — that is the live query log — and `eval/results/live/live-<ts>.json` indexes the
answers and trace ids.

```bash
python eval/live_queries.py --api http://rahbar.local --out eval/results/live
scripts/lake.sh pull
```

**E2.** `eval/coverage.py` embeds the live queries and the golden questions with
`nomic-embed-text` (`search_query: ` prefix), takes the maximum cosine, and reports the
share above 0.70 plus the uncovered topics. The gate is an in-domain share ≥ 0.85;
the script exits 1 below it. 0.70 sits between the module level's paraphrase mean (0.786)
and unrelated mean (0.460).

**E3.** Batch B (`data/batch_b/`, 12 documents) went through verification and incremental
update on 25 Nov: 5 quarantined (3 uniqueness, 2 completeness), 1 corrupt PDF, a newer fee
version archived, 1 injection flagged; 26 chunks embedded. The fee page switched to
2027-28 and back to 2026-27 on rollback with **0** chunks re-embedded. The Part B suite was
re-run after Batch B and the rollback (`20261126T104001Z`): the library, exam, lab and
laptop questions (h04–h09) became answerable; the tuition question still answers from the
current 2026-27 page. Reports: `eval/results/ingest/verify-*.json`, `ingest-*.json`.

**E4.** Eight questions in `eval/build_golden.py` / `eval/golden-e4.jsonl` close the
uncovered topics: lab hours and food, library renewals, transcript (abstain — b12 was
deleted), attendance minimum and condonation, scholarships, and a fee-only transport
question (abstain — D5 showed the bus service is covered but not its fee). They are
`synthetic` and `reviewed: false` until a group member checks them.

```bash
python eval/build_golden.py
python eval/coverage.py --live <live.json> --golden eval/golden-e4.jsonl \
  --out eval/results/coverage-e4
```

`golden.jsonl` deliberately stays at 34 questions: the release gate compares against a
baseline produced on that set. The coverage set grows to 42.

**E3 (final candidate rebuild).** The restored PVC had lost `state/registry.json`, so the
final candidate was rebuilt with a full verification Job (`20261127T140208Z`, 23 documents
checked: 14 indexed, 2 archived by recency, 7 quarantined, 1,032 chunks embedded). Because
b09 arrived with the mirror, the 2026-27 fee page was archived; the baseline has it current,
so `_restore.txt` was queued and a 4.7 s reconcile-only run relabelled 13 chunks with
**0** chunks embedded. The final gpt-oss candidate at `TOP_K=6` reached recall@5 0.9643,
MRR 0.8244, false abstention 0.0714 and faithfulness 0.9615, passing the gate against the
original Part B baseline. Report: `eval/results/suite/ragops-20261128T115331Z.json`.

## Part F (release side): F2 gate and F3 controlled release

`k8s/release/` holds the candidate ingest Jobs, `api-candidate` Deployment + Service, its
NetworkPolicies, and the two eval Jobs. The candidate is never behind the Ingress and can
only be reached by the eval Job. The release decision:

```bash
# passing candidate -> live api
kubectl -n rahbar set env deploy/api \
  CHROMA_COLLECTION=rahbar-cand-topk6 TOP_K=6 LLM_MODEL=openai/gpt-oss-20b
kubectl -n rahbar rollout status deploy/api          # maxUnavailable: 0
kubectl -n rahbar exec -i deploy/api -- python - <<'PY'
import httpx
r = httpx.post('http://127.0.0.1:8000/api/ask',
               json={'question': 'What CGPA does an undergraduate need to stay off academic warning?'},
               timeout=120)
print(r.json()['trace_id'])
PY
kubectl -n rahbar rollout undo deploy/api            # back to rahbar@4dcc91100345
kubectl -n rahbar rollout status deploy/api
```

Every trace records `collection.name`, `collection.index_id` and `embedding.version`, so
the rollback is visible in the data itself, not just in a Deployment spec. The passing
rollout trace `032c49156c244bd2ac02eba71d74b2f8` shows `rahbar-cand-topk6@7a0aa714ee0b`
and answered 2.00; after `rollout undo`, trace `3d87e6810d1e4346ba5676336be34c0a` shows
`rahbar@4dcc91100345` with the same embedding version. The deliberately bad `cs300`
release and its undo are kept in `docs/evidence/f3-rollout.txt` / `f3-rollback.txt`.
Evidence: `docs/evidence/a3/F3-rollout-topk6.txt`, `F3-rollback-topk6.txt`.

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
| C | candidate collection `rahbar-cand-cs100` (CHUNK_SIZE 100, overlap 20) | — | 14 docs | 1262 | deliberately bad: used for the gate-fails demo | 55 s |
| C | regenerate the lake registry from the restored PVC | 23 checked (14 index, 2 archive, 7 quarantine) | — | 1032 | full verify + OCR, then fee page restored; `rahbar-cand-topk6` | 2260 s |
| C | `TOP_K=6` candidate suite (`20261128T115331Z`, gpt-oss) | — | — | — | gate PASS against original Part B baseline | 10 min |

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

### D: answers and traces with the Groq key set

Six questions (`docs/evidence/a3/D-sample-answers.json`):

| Question | Answered | Behaviour |
| --- | --- | --- |
| CGPA to stay off academic warning | yes | 2.00, cites 5.4 Academic Warning/Probation (2026 handbook) |
| Until when can a student withdraw | yes | "last day of the makeup week" (2026, current edition) |
| Is attendance optional? | yes | "No", cites 1 / 1.21 Attendance; the injected b10 chunks were dropped by the rail |
| What did the 2023 rules say about withdrawal | yes | "last day of classes": the archived 2023 version, because the question asks for it |
| How do I apply for a hostel room | no | the model declined (not in the corpus) |
| Capital of France | no | relevance floor: abstained without a model call |

- D1: full record for the CGPA answer: `docs/evidence/a3/D1-full-trace-record.json`.
- D2: `trace_show d2ca42d6` rebuilds the prompt, hash **MATCH**
  (`D2-trace-show-answered.txt`); a cache-hit trace prints without a prompt
  (`D2-trace-show-cache-hit.txt`).
- **Found and fixed on the cluster:** `trace_show` crashed on cache-hit traces (their
  retrieved list had no `rank`). Both the trace writer and the tool are fixed, with a test.
- F4: the same records are in `kubectl logs` (`F4-trace-in-kubectl-logs.txt`).

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
| chroma-0 | 2–24m | 106–107 Mi with two collections; **159 Mi** with three (1,032 + 834 + 1,262 chunks) | 25m / 192Mi → 500m / 384Mi |
| redis | 24m | 9 Mi | (from A2) |
| ingest Job | — | peak RSS **111 Mi** (embedding 1,262 chunks, 55 s); **85 Mi** (no-op nightly run, 4.4 s); OCR peak from A2: 186 Mi / 1411m | 250m / 256Mi → 1500m / 512Mi |

metrics-server samples about once a minute, so a Job that finishes in under a minute is
never caught by `kubectl top`; the Job therefore logs its own peak RSS (`peak_rss_mb` in
the `ingestion finished` line, `docs/evidence/a3/C-candidate-cs100-reconcile.txt`,
`F5-ingest-nightly-noop.txt`). The 256Mi request covers the largest measured peak (OCR);
the 512Mi limit is 2.7x it.
Chroma's request was raised from 96Mi to 192Mi to cover the measured 159 Mi with three collections (k8s/base/chroma-statefulset.yaml).

## Tests

`make test` (or `cd indexer && pytest`, `cd api && pytest`): 28 indexer tests (8 new for
Part A) and 46 api tests (6 new for Part D), no network, no model.
