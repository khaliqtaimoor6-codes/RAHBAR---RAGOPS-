# Assignment 03: work split and handoff

Repo: <https://github.com/khaliqtaimoor6-codes/RAHBAR---RAGOPS-> (Assignment 02 code is
the first commit, imported unchanged). Assignment 03 needs commits from both of us, and
both of us must be able to explain every part at the demo, so read
[RAGOPS.md](RAGOPS.md) for the parts below that are already done.

## Who does what

| Part | Owner | Status |
| --- | --- | --- |
| A1 verification, A2 incremental update, Batch B | Taimoor | code + tests done; cluster run pending |
| D1–D4 traces, trace tool, metrics, guardrail logging | Taimoor | code + tests done; cluster run pending |
| F1 PVCs, F2 ingestion Job + CronJob, F4 traces on stdout + volume | Taimoor | manifests done |
| F5 resources for api / chroma / ingest Job | Taimoor | measure on the cluster |
| **B** offline testing at three levels | **Ali** | to do |
| **C** change experiment + release gate | **Ali** | to do |
| **E** drift and coverage checking | **Ali** | to do |
| **F2 (eval part)** eval Job + gate thresholds as a ConfigMap | **Ali** | to do |
| **F3** controlled release: candidate Deployment/Service/collection, rollout, undo | **Ali** | to do |
| **D5** root cause from one trace | **Ali** (needs a Part B failure) | to do |
| G report | both: each writes the sections for their parts | to do |

## Setup on your laptop

```bash
git clone https://github.com/khaliqtaimoor6-codes/RAHBAR---RAGOPS-.git rahbar && cd rahbar
git checkout -b ali/part-b-c-e          # open a PR into main when a part works
make install && make test               # 28 + 46 tests, no cluster needed
```

Cluster: `make cluster` (now 3 GB / 2 CPUs), Ollama on the host with
`OLLAMA_HOST=0.0.0.0` and `ollama pull nomic-embed-text`, `make images`, then the steps
in [k8s/README.md](../k8s/README.md). The ingestion Job is now `job/ingest` (was
`job/indexer`); `make index` runs it again.

## What you can build on

* **`trace_id` in every `/api/ask` response.** Join each eval answer to its trace.
  Traces have `latency_ms` per stage (for p50/p95), `grounding.top1_score`, `context` (the
  exact chunks the model saw, for the faithfulness judge) and `collection` /
  `embedding.version` (for F3: after `rollout undo`, a new trace must show the previous
  collection and embedding version).
* **`retrieved[].doc_id`** in the response: recall@k / MRR / nDCG by document.
* **Candidate collections for Part C / F3**: a reconcile of the same lake into another
  collection, with other settings. No re-download, no re-OCR (the lake caches extracted
  text):
  ```bash
  kubectl -n rahbar create job ingest-cand --from=cronjob/ingest --dry-run=client -o yaml \
    | yq '.spec.template.spec.containers[0].args = ["--reconcile-only"]
          | .spec.template.spec.containers[0].env = [{"name":"CHROMA_COLLECTION","value":"rahbar-cand"},
                                                     {"name":"CHUNK_SIZE","value":"300"}]' \
    | kubectl apply -f -
  ```
  (or write `k8s/release/candidate-ingest-job.yaml` with those two env vars; env wins
  over envFrom). Then the candidate Deployment `api-candidate` sets
  `CHROMA_COLLECTION=rahbar-cand` and gets its own Service. An embedding-model change
  must use a new collection name: reconcile refuses to mix models in one collection.
* **Batch B for E3**: `scripts/lake.sh upload data/batch_b && scripts/lake.sh ingest`.
  It archives the 2026-27 fee page (b09 is a newer version), adds 6 documents and
  quarantines 6. Golden questions about fees should change answer (2027-28 numbers):
  that is the drift to report. `scripts/lake.sh restore fee-structure-page` rolls it back.
* **Injected document for D4/B**: b10 (attendance notice). Ask "Is attendance optional?"
  after Batch B: the trace's `guardrails` shows `retrieval_injection ... dropped`.
* **Root cause for D5**: `kubectl -n rahbar exec deploy/api -- python -m
  app.tools.trace_show <trace_id>` prints the chunks, versions, filters and the exact
  prompt for one answer.

## Your parts in detail (from the assignment)

### Part B (`eval/`)
- `eval/golden.jsonl`: ≥25 questions; ≥15 answerable with ground-truth `doc_id` and page,
  ≥5 unanswerable (must abstain: hostel, transport, off-topic), ≥5 hard (paraphrased,
  multi-chunk, or from Batch B). ≥8 written by hand, each labelled `human`/`synthetic`,
  ≥8 synthetic ones reviewed by hand. `eval/golden.yaml` from Assignment 02 (21 questions)
  is a starting point.
- Module level: ≥15 paraphrase pairs vs ≥15 unrelated pairs through Ollama
  (`POST /api/embed`, model `nomic-embed-text`, prefix `search_query: `): mean cosine
  each, the gap, ms per chunk, determinism (same text twice, max abs difference).
- Component level: recall@3, recall@5, MRR, nDCG@5; noise test (≥3 irrelevant docs via
  the inbox, or typos in queries) and the change per metric.
- End-to-end: faithfulness (LLM judge on `context` from the trace, ≥8 hand labels and
  the agreement rate), abstention correctness, citation validity, latency p50/p95.
- Stochasticity: fixed seeds, run twice, difference per metric, explain the rest
  (temperature 0.2, Groq nondeterminism).
- One command writes `eval/results/<timestamp>.json` + a summary table.

### Part C
- C1 one change (suggest chunk size 150 → 300, or top-k 5 → 3) on baseline vs candidate,
  all three levels.
- C2 `eval/gate.yaml` thresholds (recall@5 drop ≤ 2 points, faithfulness ≥ x, p95 ≤ y,
  abstention ≥ baseline), a script that exits pass/fail; one failing candidate (a bad one
  is fine, e.g. top_k=1) and one passing.

### Part E
- E1 ≥40 live queries (≈28 in domain, ≥12 off-topic), E2 coverage against the golden set
  with a justified threshold, uncovered queries grouped into topics, E3 drift after
  Batch B, E4 ≥6 new golden questions, coverage rises, a script exits non-zero below the
  threshold.

### F2 (eval) and F3
- `k8s/eval-job.yaml` (`kubectl apply -f k8s/eval-job.yaml`): runs the suite against the
  api Service, writes the result file to a volume (`rahbar-traces` or a new
  `rahbar-results` PVC), exits non-zero when the gate fails. Thresholds in a ConfigMap;
  show that editing it changes the outcome without rebuilding the image.
- F3: `api-candidate` Deployment + Service + own collection; eval Job against it; if the
  gate passes, roll the live `api` Deployment (`maxUnavailable: 0` is already set) and
  watch `kubectl rollout status`; show a candidate stopped by the gate, and a bad release
  reversed with `kubectl rollout undo` followed by a trace that shows the previous
  collection and embedding version.

## The report

`docs/report/RAHBAR-A3-Report.docx` is the final report. Taimoor's parts (A, D, F data
side, short answers a/c/f, contribution row) and his screenshots in the appendix are done.
Everything still to write is **highlighted yellow and starts with [ALI]**: fill those in
Word, add your screenshots to the appendix (landscape pages), agree on the AI statement,
fill both roll numbers, then File → Save As → PDF. The main text must stay within 8 pages
(it is 4 now); the appendix does not count. `scripts/capture_screenshots.ps1` shows how
the screenshots were taken from real terminal windows, if you want to do yours the same way.

## Things to keep in mind

* Commit results under `eval/results/` and trace samples under `traces/` (the
  assignment asks for both). `scripts/lake.sh pull` copies the ingestion reports and the
  cluster's traces into the repo.
* Every number in the report must come from our own runs.
* The README must list the exact command for each part A–F. Parts A, D and F (data side)
  are in RAGOPS.md; add yours there or in the README.
