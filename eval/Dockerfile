# RAHBAR eval image: the Part B suite as a Kubernetes Job (k8s/eval-job.yaml).
#   docker build -t rahbar-eval:dev eval
FROM python:3.12.16-slim-trixie
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install httpx==0.28.1 pyyaml==6.0.2 \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin rahbar
WORKDIR /app/eval
COPY ragops_suite.py gate.py gate-thresholds.yaml judge_agreement.py golden.jsonl module_pairs.json ./
# The Part B baseline the release gate compares against (C2). The thresholds themselves
# are NOT baked in: they come from the rahbar-gate ConfigMap, so editing it flips a decision
# without a rebuild.
COPY results/suite/ragops-20261126T104001Z-rejudged-1.json ./baseline-a3.json
USER 10001
ENTRYPOINT ["python", "ragops_suite.py"]
