# Assignment 03: handoff to Ali

Repo: <https://github.com/khaliqtaimoor6-codes/RAHBAR---RAGOPS-> (the Assignment 02 code is
the first commit). The assignment needs commits from both of us, and both of us must be
able to explain every part at the demo, so read [RAGOPS.md](RAGOPS.md) for the parts that
are done before you start.

## Where things stand

| Part | Owner | Status |
| --- | --- | --- |
| **A** verification, incremental update, Batch B | Taimoor | ✅ done, run on the cluster |
| **B** golden set (34), three-level suite, two seeded runs | Taimoor | ✅ done, results in `eval/results/suite/` |
| **D1–D4** traces, trace tool, metrics, guardrail logging | Taimoor | ✅ done |
| **D5** root cause from one trace | Taimoor | ✅ done (a02, RAGOPS.md → Part B) |
| **F1, F2 (ingestion + eval Jobs), F4, F5** | Taimoor | ✅ done |
| CI (lint, tests, manifests, build, Trivy, e2e on k3d) | Taimoor | ✅ green on `dev` and `main` |
| **B hand work**: review ≥ 8 synthetic questions, label ≥ 8 judge verdicts | **both** | ⬜ `eval/REVIEW-SYNTHETIC.md` |
| **C1** one pipeline change, baseline vs candidate, all three levels | **Ali** | ⬜ |
| **C2** release gate: thresholds in a config file, script exits pass/fail | **Ali** | ⬜ |
| **F2 (gate part)** thresholds as a ConfigMap; eval Job fails when the gate fails | **Ali** | ⬜ |
| **E1–E4** live query log, coverage, drift, close the gap | **Ali** | ⬜ |
| **F3** candidate Deployment + Service + collection, rollout, undo | **Ali** | ⬜ |
| **G** report | both | Taimoor's sections written; yours are **yellow `[ALI]`** |

## How we work in git

`main` only changes through a pull request from `dev`, and `dev` only through pull
requests from our own branches. CI runs on every push to `dev` and on every pull request
into `main`.

```bash
git clone https://github.com/khaliqtaimoor6-codes/RAHBAR---RAGOPS-.git rahbar && cd rahbar
git checkout -b ali origin/dev            # your branch, from dev
# ... small commits, one change each, the reason in the message ...
git push -u origin ali
```

Then on GitHub: **pull request `ali` → `dev`**, merge when it looks right, check that CI on
`dev` is green, and open a **pull request `dev` → `main`**. Before each new piece of work:
`git fetch && git merge origin/dev` on your branch. Taimoor works on `taimoor` the same way.

## Setup on your laptop (once)

You need Docker, kubectl, Python 3.12, [Ollama](https://ollama.com) and a free
[Groq API key](https://console.groq.com/keys) (copy it from the popup when you create it:
Groq never shows it again).

```bash
python -m venv .venv && .venv/bin/pip install -r api/requirements-dev.txt -r indexer/requirements-dev.txt
(cd api && ../.venv/bin/pytest -q) && (cd indexer && ../.venv/bin/pytest -q)   # 50 + 30 tests, no cluster
ollama pull nomic-embed-text              # embeddings only (~270 MB); answers come from Groq
```

**Cluster: minikube** (what Taimoor uses):
```bash
minikube start --driver=docker --cni=calico --memory=3072 --cpus=2 --disk-size=12g
minikube addons enable metrics-server && minikube addons enable ingress
make images                               # api, indexer, ui, eval -> loaded into minikube
```
**or k3d** (if minikube does not fit in your RAM): `make k3d-up k3d-images`, and use
`k8s/overlays/k3d` instead of `k8s/overlays/dev` below.

Pods reach Ollama on the host at `host.minikube.internal:11434`; Ollama can stay on its
default `127.0.0.1`.

**Deploy:**
```bash
kubectl apply -f k8s/base/namespace.yaml
# the Groq key: save it in a file with no newline, then
kubectl -n rahbar create secret generic rahbar-secret --from-file=LLM_API_KEY=groq.txt
rm groq.txt
kubectl apply -k k8s/overlays/dev
kubectl -n rahbar wait --for=condition=complete job/ingest --timeout=60m   # ~6 min: download, OCR, verify, index
kubectl -n rahbar rollout status deploy/api
```
Then bring your cluster to the same state as Taimoor's (Batch B ingested, fee page rolled
back), so your numbers are comparable with Part B's:
```bash
scripts/lake.sh upload data/batch_b && scripts/lake.sh ingest
scripts/lake.sh restore fee-structure-page && scripts/lake.sh ingest
scripts/lake.sh upload data/demo_batch_c && scripts/lake.sh ingest
```
On Windows use `.\scripts\lake.ps1 ...` from PowerShell (plain `bash` there is WSL's, which
has no kubectl config).

## Your parts, and what is already there for them

### C1: one change, baseline vs candidate
- Pick the change. Suggested: chunk size 150 → 300 (a passing-looking candidate) and
  150 → 100 or `TOP_K` 5 → 1 (a deliberately bad one).
- Build the candidate's collection from the lake (no re-download, no re-OCR):
  ```bash
  kubectl -n rahbar create job ingest-cand-cs300 --from=cronjob/ingest --dry-run=client -o json \
    | python -c "import json,sys; j=json.load(sys.stdin); c=j['spec']['template']['spec']['containers'][0]; \
  c['args']=['--reconcile-only']; c['env']=[{'name':'CHROMA_COLLECTION','value':'rahbar-cand-cs300'}, \
  {'name':'CHUNK_SIZE','value':'300'},{'name':'CHUNK_OVERLAP','value':'50'}]; \
  j['spec']['template']['spec']['initContainers']=[]; print(json.dumps(j))" | kubectl apply -f -
  ```
  Better: commit it as `k8s/release/candidate-ingest-job.yaml`. An embedding-model change
  needs a new collection name; reconcile refuses to mix models in one collection.
- The candidate api: a copy of the `api` Deployment named `api-candidate`, with
  `CHROMA_COLLECTION=rahbar-cand-cs300` (and the changed setting) as env, its own Service,
  and the NetworkPolicies extended to it (`app: api-candidate`, or keep the label `app: api`
  plus a `track: candidate` label and select on that).
- Run the suite against it: in `k8s/eval-job.yaml` set `API_URL` to the candidate's
  Service. Baseline = the same Job against `http://api:8000`.

### C2 + F2 gate: thresholds as a ConfigMap, the eval Job fails when the gate fails
- The result file has everything the gate needs:
  `runs[0].component.clean["recall@5"]`, `runs[0].end_to_end.faithfulness`,
  `runs[0].end_to_end.latency_p95_ms`, `runs[0].end_to_end.abstention_correct_unanswerable`
  (and the same for the baseline's file).
- Write `eval/gate.py`: read the candidate's and the baseline's result JSON and the
  thresholds (e.g. recall@5 may drop ≤ 2 points, faithfulness ≥ a value you justify, p95 ≤
  a value you justify, abstention ≥ baseline), print pass/fail per rule, exit 1 on failure.
- Put the thresholds in a ConfigMap (`k8s/gate-config.yaml`), mount it into the eval Job,
  and call the gate at the end of `eval/ragops_suite.py` (or as a second container step).
  Show: one candidate fails, one passes, and editing the ConfigMap flips the result without
  rebuilding the image.
- Part B's numbers to start from (Taimoor's cluster, run `20261126T104001Z`): recall@5
  0.964, MRR 0.830, faithfulness 1.0 (25/28 judged), abstention on unanswerable 0.833,
  p95 13.7 s.

### E1–E4: drift and coverage
- E1: ≥ 40 queries "as if from users": ~28 in the golden set's domain, ≥ 12 off-topic.
  Put them in `eval/live_queries.jsonl` and send them through `/api/ask`: they land in the
  traces, which are the live query log.
- E2: for each live query, the most similar golden question (embed both with
  `nomic-embed-text` through Ollama, `search_query: ` prefix; the suite's `Embedder` class
  does this). Report the share above a threshold you justify, list the uncovered queries by
  topic.
- E3: Batch B is already on Taimoor's cluster; on a fresh cluster ingest it, re-run the
  suite, and report what changed and why (fees switch to 2027-28 until the rollback;
  library/exam/lab questions become answerable).
- E4: ≥ 6 new golden questions from the uncovered topics (add them to
  `eval/build_golden.py`, labelled synthetic or human), re-run coverage, show it rises; a
  script exits non-zero below your threshold. Include a **fee-only transport question**
  as a new abstain case: D5 showed a02's "bus routes" half is answerable.

### F3: controlled release
- The candidate from C runs as `api-candidate` with its own Service and collection; the
  eval Job runs against it; if the gate passes, roll the live `api` Deployment to the
  candidate's settings (`maxUnavailable: 0` is already set) and watch
  `kubectl rollout status deploy/api`.
- Show a candidate stopped by the gate (never rolled out), and a bad release reversed with
  `kubectl rollout undo deploy/api`, then a new trace showing the previous collection and
  embedding version: every trace has `collection.name`, `collection.index_id` and
  `embedding.version`:
  ```bash
  kubectl -n rahbar logs deploy/api | grep rahbar.trace | tail -1
  kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show <trace_id>
  ```

### Hand work (both of us): `eval/REVIEW-SYNTHETIC.md`
Review ≥ 8 of the 13 synthetic questions against the documents, and label ≥ 8 of the 12
answers in `eval/results/suite/judge-hand-labels-20261126T104001Z.csv` by hand; then
`python eval/judge_agreement.py <csv>` gives the agreement figure for the report.

## Tools you will use

| What | Command |
| --- | --- |
| run the Part B suite | `kubectl -n rahbar delete job eval --ignore-not-found; kubectl apply -f k8s/eval-job.yaml` |
| quick run while developing | add env `RUNS=1` and `ONLY=g01,a05,h04` to the Job |
| re-score a saved run (no questions asked again) | env `REJUDGE=/results/ragops-<ts>.json` |
| copy results / traces / reports into the repo | `scripts/lake.sh pull` |
| retrieval only, no LLM | `POST /api/retrieve {"question": ...}` |
| skip the semantic cache | header `X-RAHBAR-Cache: bypass` on `/api/ask` |
| print the exact prompt of any answer | `kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show <id>` |
| metrics over a window | `kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_summary --since 1h` |
| report screenshots from real terminal windows (Windows) | `.\scripts\capture_screenshots.ps1` (add your shots to its table) |

## Things that will bite you

- **Groq free tier**: one full two-run suite uses most of a day's tokens for
  `openai/gpt-oss-20b`. Develop with `RUNS=1` and `ONLY=...`; use `REJUDGE` to re-score;
  run the full baseline and candidate suites once each, on different days if needed. When
  the quota is gone, the judge and the answers degrade into "rate-limited"/fallbacks: check
  `fallbacks` and `faithfulness_judged` in the result before trusting a run.
- **A finished Job cannot be re-applied** (`field is immutable`): delete it first, or use
  `kubectl create job --from=cronjob/ingest <new-name>` for ingestion.
- Every number in the report must come from our own runs, and the result files must be
  committed (`eval/results/`, `traces/`).
- The README must give the exact command for each part A–F: A, B, D, F are in RAGOPS.md;
  add C and E there.

## The report

`docs/report/RAHBAR-A3-Report.docx`. Everything still to write is **highlighted yellow and
starts with `[ALI]`**: Figure 3 row "check coverage", 4.4 (Part C and the release
decision), 4.6 (Part E), the F2 gate and F3 rows, short answer (e), your contribution row,
the judge agreement figure, your screenshots (C gate fail/pass, E coverage before/after,
F gate result after a ConfigMap edit, `rollout status` and `rollout undo` with a trace).
Then both roll numbers, agree on the AI statement, and File → Save As → PDF. The main text
is 5 pages now and must stay ≤ 8; the appendix does not count.
