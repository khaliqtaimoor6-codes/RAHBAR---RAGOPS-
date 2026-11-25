#!/usr/bin/env bash
# Operator commands for the data lake on the cluster (Part A / F). Works from Git Bash on
# Windows too. Everything goes through the lake-shell pod; only the ingestion Job ever
# writes to the vector store.
#
#   scripts/lake.sh upload data/batch_b      copy a batch into the inbox
#   scripts/lake.sh delete <doc_id>          queue a document for deletion
#   scripts/lake.sh restore <doc_id>         queue a rollback to an archived version
#   scripts/lake.sh ingest                   run the ingestion Job now and follow its log
#   scripts/lake.sh ls [path]                list a lake folder (default: the top level)
#   scripts/lake.sh pull                     copy reports and traces into the repo
#                                            (eval/results/ingest/, traces/)
set -euo pipefail
NS=${NS:-rahbar}
HERE=$(cd "$(dirname "$0")/.." && pwd)

shell_up() {
  if ! kubectl -n "$NS" get pod lake-shell >/dev/null 2>&1; then
    kubectl apply -f "$HERE/k8s/tools/lake-shell.yaml" >/dev/null
  fi
  kubectl -n "$NS" wait --for=condition=Ready pod/lake-shell --timeout=120s >/dev/null
}

case "${1:-}" in
  upload)
    src=${2:?usage: lake.sh upload <dir>}
    shell_up
    name=$(basename "$src")
    kubectl -n "$NS" cp "$src" "lake-shell:/data/lake/inbox/$name"
    echo "copied $(ls "$src" | wc -l) file(s) into inbox/$name; now: scripts/lake.sh ingest"
    ;;
  delete|restore)
    id=${2:?usage: lake.sh $1 <doc_id>}
    shell_up
    kubectl -n "$NS" exec lake-shell -- sh -c "echo '$id' >> /data/lake/inbox/_$1.txt"
    echo "queued: $1 $id (applied by the next ingestion run: scripts/lake.sh ingest)"
    ;;
  ingest)
    job="ingest-$(date +%s)"
    kubectl -n "$NS" create job --from=cronjob/ingest "$job"
    kubectl -n "$NS" wait --for=condition=Ready pod -l job-name="$job" --timeout=300s || true
    kubectl -n "$NS" logs -f "job/$job" -c ingest
    kubectl -n "$NS" wait --for=condition=complete "job/$job" --timeout=3600s
    ;;
  ls)
    shell_up
    kubectl -n "$NS" exec lake-shell -- ls -la "/data/lake/${2:-}"
    ;;
  pull)
    shell_up
    mkdir -p "$HERE/eval/results/ingest" "$HERE/traces"
    kubectl -n "$NS" cp lake-shell:/data/lake/reports "$HERE/eval/results/ingest"
    kubectl -n "$NS" cp lake-shell:/traces "$HERE/traces/cluster"
    echo "reports -> eval/results/ingest/, traces -> traces/cluster/"
    ;;
  *)
    sed -n '2,13p' "$0"; exit 2 ;;
esac
