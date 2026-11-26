# RAHBAR eval image: the Part B suite as a Kubernetes Job (k8s/eval-job.yaml).
#   docker build -t rahbar-eval:dev eval
FROM python:3.12.16-slim-trixie
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install httpx==0.28.1 \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin rahbar
WORKDIR /app/eval
COPY ragops_suite.py judge_agreement.py golden.jsonl module_pairs.json ./
USER 10001
ENTRYPOINT ["python", "ragops_suite.py"]
