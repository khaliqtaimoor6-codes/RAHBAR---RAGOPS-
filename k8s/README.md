# From a fresh cluster to a working pipeline

Everything is in `k8s/`: `base/` (all objects), `overlays/dev` (minikube on a laptop),
`overlays/ci`, `overlays/k3d`, `overlays/prod`, and `tools/lake-shell.yaml` (operator pod).

## Once per laptop

```bash
make cluster                     # minikube: docker driver, Calico, 3 GB, 2 CPUs, + metrics-server, ingress
OLLAMA_HOST=0.0.0.0 ollama serve # embeddings only; listens where minikube can reach it
ollama pull nomic-embed-text     # ~270 MB; no chat model is pulled (answers come from Groq)
make images                      # build rahbar-api, rahbar-indexer, rahbar-ui :dev, load into minikube
```

## Apply

```bash
kubectl apply -f k8s/base/namespace.yaml
export LLM_API_KEY=gsk_...  && make secret          # the Groq key, never in a file
kubectl apply -k k8s/overlays/dev                   # everything, including the ingest Job
kubectl -n rahbar wait --for=condition=complete job/ingest --timeout=60m
kubectl -n rahbar rollout status deploy/api
```

The first ingestion downloads the corpus into the `rahbar-lake` PVC, OCRs the scanned
PDFs, verifies, and indexes (~20 min on a laptop CPU). Until it finishes the api pods are
Running but 0/1 READY (no collection yet). Later runs reuse the lake and embed only what
changed.

Re-applying after the first run prints `The Job "ingest" is invalid ... field is
immutable`: a finished Job cannot be changed. Everything else is applied. To re-run
ingestion use `scripts/lake.sh ingest` (a new Job from the CronJob, which does carry the
changes); to replace the Job object itself, `kubectl -n rahbar delete job ingest` first.

## Check

```bash
kubectl -n rahbar get all,pvc,configmap,cronjob,job
kubectl -n rahbar logs job/ingest -c ingest | tail -40            # verification table + counts
make ask Q="What CGPA does an undergraduate need to stay off academic warning?"
kubectl -n rahbar logs deploy/api | grep '"rahbar.trace"' | tail -1
```

## Day-2 operations

| Task | Command |
| --- | --- |
| run ingestion now | `scripts/lake.sh ingest` (or `make index`) |
| ingest a new batch | `scripts/lake.sh upload <dir> && scripts/lake.sh ingest` |
| delete a document | `scripts/lake.sh delete <doc_id> && scripts/lake.sh ingest` |
| roll back to an archived version | `scripts/lake.sh restore <doc_id> && scripts/lake.sh ingest` |
| copy reports and traces into the repo | `scripts/lake.sh pull` |
| rebuild a prompt from a trace | `kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show <id>` |
| summarise traces | `kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_summary --since 1h` |
| metrics | `kubectl -n rahbar port-forward svc/api 8000:8000` then `curl localhost:8000/metrics` |
