"""Part B: the offline test suite at three levels (RAGOps paper 4.2.5, Table 1).

One command runs everything and writes eval/results/ragops-<timestamp>.json plus a
summary table (.md); on the cluster it is the eval Job (kubectl apply -f k8s/eval-job.yaml).

    python eval/ragops_suite.py --api http://localhost:8000 --ollama http://localhost:11434

Levels:
  module      embedding model alone: mean cosine of 15 paraphrase vs 15 unrelated pairs and
              the gap; embedding time per chunk; determinism (same text twice, max diff)
  component   retrieval alone (POST /api/retrieve, no LLM): recall@3, recall@5, MRR,
              nDCG@5 against ground-truth (document, page); then a noise test with
              seeded typos in the questions and the change per metric
  end-to-end  the full pipeline (POST /api/ask, cache bypassed): faithfulness (an LLM
              judge reads the exact context from the answer's trace), abstention
              correctness on unanswerable questions, citation validity, latency p50/p95
Stochasticity: --runs 2 repeats everything with the same seeds and reports the difference
per metric.

Ground truth: a retrieved chunk is relevant when its doc_id is a ground-truth document and
its page is one of that document's ground-truth pages (eval/golden.jsonl).

Faithfulness labels by hand: the suite writes judge-hand-labels-<ts>.csv; a group member
fills `human_label`, then eval/judge_agreement.py reports how often the judge agrees.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

HERE = Path(__file__).resolve().parent
QUERY_PREFIX = {"nomic-embed-text": "search_query: "}
DOC_PREFIX = {"nomic-embed-text": "search_document: "}

JUDGE_PROMPT = """You check whether an answer is supported by the context it was given.
Reply with a JSON object only: {"supported": true|false, "unsupported_claims": [..]}.
"supported" is true only if every factual claim in the answer is stated in the context.
An answer that says the documents do not cover the question is supported.

<context>
%s
</context>

<question>%s</question>
<answer>%s</answer>"""


# ----------------------------------------------------------------------------- helpers

def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)


def mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 4) if values else None


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def load_golden(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
                "seven": "7", "eight": "8", "nine": "9", "ten": "10"}


def normalise(text: str) -> str:
    """Lower case, number words as digits, no space inside numbers or before %, and
    typographic quotes/hyphens folded, so '6 years' matches 'six years' and '100%'
    matches '100 %' (which the model wrote with a narrow no-break space)."""
    t = text.lower().replace("\u202f", " ").replace("\u00a0", " ")
    t = t.replace("\u2019", "'").replace("\u2011", "-").replace("\u2010", "-")
    t = re.sub(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", lambda m: NUMBER_WORDS[m.group(1)], t)
    t = re.sub(r"(\d)\s+%", r"\1%", t)
    return re.sub(r"\s+", " ", t)


def expect_hit(expect: str | None, answer: str) -> bool | None:
    return normalise(expect) in normalise(answer) if expect else None


def is_relevant(ref: dict[str, Any], gt: list[dict[str, Any]]) -> bool:
    doc = ref.get("doc_id") or Path(str(ref.get("source", ""))).stem
    return any(doc == g["doc_id"] and ref.get("page") in g["pages"] for g in gt)


def typo(question: str, rng: random.Random) -> str:
    """Swap two adjacent letters in about one word in three of length >= 5 (seeded)."""
    words = question.split()
    for i, w in enumerate(words):
        core = re.sub(r"\W", "", w)
        if len(core) >= 5 and not any(c.isdigit() for c in w) and rng.random() < 0.34:
            j = rng.randrange(1, len(w) - 2)
            words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words)


# ----------------------------------------------------------------------------- module

class Embedder:
    def __init__(self, url: str, model: str) -> None:
        self.url = url.rstrip("/") + "/api/embed"
        self.model = model
        self.client = httpx.Client(timeout=120)

    def embed(self, texts: list[str], prefix: str) -> list[list[float]]:
        r = self.client.post(self.url, json={"model": self.model, "truncate": True,
                                             "input": [prefix + t for t in texts]})
        r.raise_for_status()
        return r.json()["embeddings"]


def module_level(emb: Embedder, chunk_texts: list[str]) -> dict[str, Any]:
    pairs = json.loads((HERE / "module_pairs.json").read_text(encoding="utf-8"))
    qp = QUERY_PREFIX.get(emb.model.split(":")[0], "")
    dp = DOC_PREFIX.get(emb.model.split(":")[0], "")
    emb.embed(["warm-up"], qp)                        # load the model before timing anything

    def sims(kind: str) -> list[float]:
        out = []
        for a, b in pairs[kind]:
            va, vb = emb.embed([a, b], qp)
            out.append(cosine(va, vb))
        return out

    para, unrel = sims("paraphrase"), sims("unrelated")
    texts = chunk_texts[:30] or [p[0] for p in pairs["paraphrase"]]
    started = time.perf_counter()
    for t in texts:                                   # one request per chunk: the query-time cost
        emb.embed([t], dp)
    per_chunk_ms = (time.perf_counter() - started) * 1000 / len(texts)
    started = time.perf_counter()
    emb.embed(texts, dp)                              # batched, as the ingestion Job does
    batched_ms = (time.perf_counter() - started) * 1000 / len(texts)
    first, second = emb.embed(texts[:10], dp), emb.embed(texts[:10], dp)
    max_diff = max(abs(x - y) for va, vb in zip(first, second) for x, y in zip(va, vb))
    return {"paraphrase_pairs": len(para), "unrelated_pairs": len(unrel),
            "paraphrase_mean_cosine": mean(para), "unrelated_mean_cosine": mean(unrel),
            "gap": round(statistics.fmean(para) - statistics.fmean(unrel), 4),
            "paraphrase_min": round(min(para), 4), "unrelated_max": round(max(unrel), 4),
            "ms_per_chunk_single": round(per_chunk_ms, 1), "ms_per_chunk_batched": round(batched_ms, 1),
            "chunks_timed": len(texts), "determinism_max_abs_diff": max_diff}


# -------------------------------------------------------------------------- component

def retrieval_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    r3, r5, mrr, ndcg = [], [], [], []
    for row in rows:
        gt, refs = row["gt"], row["retrieved"]
        rel_flags = [is_relevant(r, gt) for r in refs[:5]]

        def recall(k: int) -> float:
            found = [g for g in gt if any(
                (r.get("doc_id") or "") == g["doc_id"] and r.get("page") in g["pages"]
                for r in refs[:k])]
            return len(found) / len(gt)

        r3.append(recall(3))
        r5.append(recall(5))
        first = next((i for i, f in enumerate(rel_flags, start=1) if f), None)
        mrr.append(1 / first if first else 0.0)
        dcg = sum(1 / math.log2(i + 1) for i, f in enumerate(rel_flags, start=1) if f)
        known = max(len(gt), sum(rel_flags))          # relevant chunks we know exist
        ideal = sum(1 / math.log2(i + 1) for i in range(1, min(5, known) + 1))
        ndcg.append(dcg / ideal if ideal else 0.0)
    return {"questions": len(rows), "recall@3": mean(r3), "recall@5": mean(r5),
            "mrr": mean(mrr), "ndcg@5": mean(ndcg)}


def component_level(client: httpx.Client, api: str, golden: list[dict[str, Any]],
                    seed: int) -> dict[str, Any]:
    answerable = [q for q in golden if q["answerable"]]
    rng = random.Random(seed)

    def run(questions: list[tuple[dict, str]]) -> list[dict[str, Any]]:
        rows = []
        for q, text in questions:
            r = client.post(api + "/api/retrieve", json={"question": text})
            r.raise_for_status()
            rows.append({"id": q["id"], "question": text, "gt": q["relevant"],
                         "retrieved": r.json()["retrieved"]})
        return rows

    clean = run([(q, q["question"]) for q in answerable])
    noisy = run([(q, typo(q["question"], rng)) for q in answerable])
    m_clean, m_noisy = retrieval_metrics(clean), retrieval_metrics(noisy)
    return {"clean": m_clean, "typos": m_noisy,
            "typo_delta": {k: round(m_noisy[k] - m_clean[k], 4)
                           for k in ("recall@3", "recall@5", "mrr", "ndcg@5")},
            "per_question": [{"id": c["id"],
                              "relevant_ranks": [i for i, r in enumerate(c["retrieved"][:5], 1)
                                                 if is_relevant(r, c["gt"])],
                              "typo_question": n["question"],
                              "typo_relevant_ranks": [i for i, r in enumerate(n["retrieved"][:5], 1)
                                                      if is_relevant(r, n["gt"])]}
                             for c, n in zip(clean, noisy)]}


# ------------------------------------------------------------------------- end-to-end

class Judge:
    def __init__(self, base_url: str, key: str, model: str, seed: int) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.key, self.model, self.seed = key, model, seed
        self.client = httpx.Client(timeout=60)

    def __call__(self, context: str, question: str, answer: str) -> dict[str, Any]:
        payload = {"model": self.model, "temperature": 0, "seed": self.seed,
                   "response_format": {"type": "json_object"}, "max_tokens": 300,
                   "messages": [{"role": "user",
                                 "content": JUDGE_PROMPT % (context[:6000], question, answer)}]}
        for attempt in range(6):
            r = self.client.post(self.url, json=payload,
                                 headers={"Authorization": f"Bearer {self.key}"})
            if r.status_code == 429:
                time.sleep(min(float(r.headers.get("retry-after", "5") or 5), 30) + attempt)
                continue
            if r.status_code == 400 and "validate JSON" in r.text and "response_format" in payload:
                # Found in the first cluster run: Groq rejects a reply that is not valid
                # JSON in JSON mode (5 of 28 answers went unjudged). Ask again without JSON
                # mode and read the first {...} object from the text.
                payload = {k: v for k, v in payload.items() if k != "response_format"}
                continue
            if r.status_code != 200:
                # e.g. 404 for a model name the provider no longer serves: record the
                # answer as not judged instead of aborting the whole run
                return {"supported": None,
                        "unsupported_claims": [f"judge HTTP {r.status_code}: {r.text[:120]}"]}
            try:
                text = r.json()["choices"][0]["message"]["content"] or ""
                m = re.search(r"\{.*\}", text, re.S)
                out = json.loads(m.group(0) if m else text)
                return {"supported": bool(out.get("supported")),
                        "unsupported_claims": out.get("unsupported_claims") or []}
            except (ValueError, KeyError):
                return {"supported": None, "unsupported_claims": ["judge output not JSON"]}
        return {"supported": None, "unsupported_claims": ["judge rate-limited"]}


def find_trace(trace_dir: Path, trace_id: str, wait_s: float = 5.0) -> dict[str, Any] | None:
    deadline = time.time() + wait_s
    while True:
        for f in trace_dir.glob("*.jsonl"):
            with f.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if trace_id in line:
                        try:
                            rec = json.loads(line)
                        except ValueError:
                            continue
                        if rec.get("trace_id") == trace_id:
                            return rec
        if time.time() > deadline:
            return None
        time.sleep(0.5)


def e2e_level(client: httpx.Client, api: str, golden: list[dict[str, Any]], judge: Judge | None,
              trace_dir: Path | None, pace: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    for q in golden:
        for attempt in range(3):
            t0 = time.perf_counter()
            r = client.post(api + "/api/ask", json={"question": q["question"]},
                            headers={"X-RAHBAR-Cache": "bypass"})
            latency = (time.perf_counter() - t0) * 1000
            r.raise_for_status()
            resp = r.json()
            trace = find_trace(trace_dir, resp["trace_id"]) if trace_dir else None
            fallback = ((trace or {}).get("grounding") or {}).get("fallback")
            if fallback != "provider_error" or attempt == 2:
                break
            time.sleep(30)                             # provider rate limit: wait, try again
        row = {"id": q["id"], "origin": q["origin"], "hard": q["hard"],
               "answerable": q["answerable"], "question": q["question"],
               "answer": resp["answer"], "answered": resp["answered_from_context"],
               "citations": resp["citations"], "retrieved": resp["retrieved"],
               "latency_ms": round(latency, 1), "trace_id": resp["trace_id"],
               "fallback": fallback, "expect": q.get("expect"),
               "expect_hit": expect_hit(q.get("expect"), resp["answer"])}
        context = "\n\n".join(f"[{c['source']} p.{c.get('page')}] {c['text']}"
                              for c in ((trace or {}).get("context") or []))
        if judge is not None and resp["answered_from_context"] and context:
            row["judge"] = judge(context, q["question"], resp["answer"])
        # citation validity: the cited chunk was retrieved for this answer, and (for an
        # answerable question) it is from a ground-truth document
        retrieved_keys = {(x["source"], x.get("page")) for x in resp["retrieved"]}
        gt_docs = {g["source"] for g in q.get("relevant", [])}
        cites = resp["citations"]
        row["citations_in_retrieved"] = (sum((c["source"], c.get("page")) in retrieved_keys
                                             for c in cites) / len(cites)) if cites else None
        row["citations_gt_doc"] = (sum(c["source"] in gt_docs for c in cites) / len(cites)) \
            if cites and gt_docs else None
        rows.append(row)
        time.sleep(pace)
    return summarise_e2e(rows), rows


def summarise_e2e(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answered = [r for r in rows if r["answered"]]
    judged = [r for r in answered if (r.get("judge") or {}).get("supported") is not None]
    unans = [r for r in rows if not r["answerable"]]
    ans = [r for r in rows if r["answerable"]]
    lat = [r["latency_ms"] for r in rows]
    summary = {
        "questions": len(rows), "answered": len(answered),
        "faithfulness": mean([1.0 if r["judge"]["supported"] else 0.0 for r in judged]),
        "faithfulness_judged": len(judged),
        "abstention_correct_unanswerable": mean([0.0 if r["answered"] else 1.0 for r in unans]),
        "false_abstention_answerable": mean([0.0 if r["answered"] else 1.0 for r in ans]),
        "citation_validity_in_retrieved": mean([r["citations_in_retrieved"] for r in answered
                                                if r["citations_in_retrieved"] is not None]),
        "citation_validity_gt_doc": mean([r["citations_gt_doc"] for r in answered
                                          if r["citations_gt_doc"] is not None]),
        "expected_string_hit": mean([1.0 if r["expect_hit"] else 0.0 for r in ans
                                     if r["expect_hit"] is not None]),
        "latency_p50_ms": pct(lat, 0.5), "latency_p95_ms": pct(lat, 0.95),
        "fallbacks": sum(1 for r in rows if r["fallback"]),
    }
    return summary


# ------------------------------------------------------------------------------- main

def one_run(args: argparse.Namespace, golden: list[dict[str, Any]], run_no: int) -> dict[str, Any]:
    client = httpx.Client(timeout=120)
    judge = None
    if args.judge_key:
        judge = Judge(args.judge_base_url, args.judge_key, args.judge_model, args.seed)
    print(f"[run {run_no}] end-to-end ({len(golden)} questions)...", flush=True)
    e2e, rows = e2e_level(client, args.api, golden, judge,
                          Path(args.traces) if args.traces else None, args.pace)
    print(f"[run {run_no}] component (retrieval + typo noise)...", flush=True)
    comp = component_level(client, args.api, golden, args.seed)
    chunk_texts = []
    if args.traces:
        seen: set[str] = set()
        for r in rows:
            for c in ((find_trace(Path(args.traces), r["trace_id"], 0) or {}).get("context") or []):
                if c["chunk_id"] not in seen:
                    seen.add(c["chunk_id"])
                    chunk_texts.append(c["text"])
    print(f"[run {run_no}] module (embedding)...", flush=True)
    mod = module_level(Embedder(args.ollama, args.embed_model), chunk_texts)
    return {"module": mod, "component": comp, "end_to_end": e2e, "answers": rows}


FLAT = [("module", "paraphrase_mean_cosine"), ("module", "unrelated_mean_cosine"),
        ("module", "gap"), ("module", "ms_per_chunk_single"), ("module", "determinism_max_abs_diff"),
        ("component.clean", "recall@3"), ("component.clean", "recall@5"),
        ("component.clean", "mrr"), ("component.clean", "ndcg@5"),
        ("component.typos", "recall@5"), ("component.typos", "mrr"),
        ("end_to_end", "faithfulness"), ("end_to_end", "abstention_correct_unanswerable"),
        ("end_to_end", "false_abstention_answerable"),
        ("end_to_end", "citation_validity_in_retrieved"), ("end_to_end", "citation_validity_gt_doc"),
        ("end_to_end", "expected_string_hit"),
        ("end_to_end", "latency_p50_ms"), ("end_to_end", "latency_p95_ms")]


def get(run: dict[str, Any], section: str, key: str) -> Any:
    node: Any = run
    for part in section.split("."):
        node = node[part]
    return node.get(key)


def table(runs: list[dict[str, Any]]) -> str:
    head = "| level | metric | " + " | ".join(f"run {i + 1}" for i in range(len(runs)))
    head += " | difference |\n" if len(runs) > 1 else " |\n"
    head += "|---|---|" + "---|" * len(runs) + ("---|\n" if len(runs) > 1 else "\n")
    lines = []
    for section, key in FLAT:
        vals = [get(r, section, key) for r in runs]
        cells = " | ".join("—" if v is None else str(v) for v in vals)
        diff = ""
        if len(runs) > 1 and all(isinstance(v, (int, float)) for v in vals):
            diff = f" | {round(vals[1] - vals[0], 4)}"
        elif len(runs) > 1:
            diff = " | —"
        lines.append(f"| {section} | {key} | {cells}{diff} |")
    return head + "\n".join(lines) + "\n"


def rejudge(path: Path, args: argparse.Namespace) -> int:
    """Re-score a saved result: the same answers (nothing is asked again), the current
    judge and expected-string matcher, the exact contexts read back from the traces.
    Writes <name>-rejudged.json/.md next to the original, which is kept."""
    result = json.loads(path.read_text(encoding="utf-8"))
    judge = Judge(args.judge_base_url, args.judge_key, args.judge_model, args.seed)
    traces = Path(args.traces)
    for i, run in enumerate(result["runs"], start=1):
        print(f"[rejudge] run {i}: {len(run['answers'])} answers", flush=True)
        for row in run["answers"]:
            row["expect_hit"] = expect_hit(row.get("expect"), row["answer"])
            rec = find_trace(traces, row["trace_id"], 0) or {}
            context = "\n\n".join(f"[{c['source']} p.{c.get('page')}] {c['text']}"
                                   for c in (rec.get("context") or []))
            if row["answered"] and context:
                row["judge"] = judge(context, row["question"], row["answer"])
                time.sleep(1)
        run["end_to_end"] = summarise_e2e(run["answers"])
    result["rejudged"] = {"from": path.name, "judge_model": args.judge_model,
                          "at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}
    out = path.with_name(path.stem + "-rejudged.json")
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    summary = table(result["runs"])
    path.with_name(path.stem + "-rejudged.md").write_text(
        f"# RAHBAR offline suite {result['timestamp']} (re-judged)\n\ncollection: "
        f"{result['collection']}\ngolden: {result['golden']}\n\n{summary}", encoding="utf-8")
    print(summary)
    print(f"wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    env = os.environ.get
    ap = argparse.ArgumentParser(description="RAHBAR offline test suite (Part B).")
    ap.add_argument("--api", default=env("API_URL", "http://localhost:8000"))
    ap.add_argument("--ollama", default=env("OLLAMA_URL", "http://localhost:11434"))
    ap.add_argument("--embed-model", default=env("EMBED_MODEL", "nomic-embed-text"))
    ap.add_argument("--golden", default=env("GOLDEN", str(HERE / "golden.jsonl")))
    ap.add_argument("--traces", default=env("TRACE_DIR", ""),
                    help="trace directory (for the judge's context); empty = no faithfulness")
    ap.add_argument("--out", default=env("RESULTS_DIR", str(HERE / "results")))
    ap.add_argument("--runs", type=int, default=int(env("RUNS", "2")))
    ap.add_argument("--seed", type=int, default=int(env("SEED", "1234")))
    ap.add_argument("--pace", type=float, default=float(env("PACE_SECONDS", "4")),
                    help="seconds between /api/ask calls (free-tier rate limits)")
    ap.add_argument("--judge-base-url", default=env("HOSTED_BASE_URL", "https://api.groq.com/openai/v1"))
    ap.add_argument("--judge-model", default=env("JUDGE_MODEL") or env("LLM_MODEL", "openai/gpt-oss-20b"),
                    help="default: the answering model (LLM_MODEL from the ConfigMap)")
    ap.add_argument("--rejudge", default=env("REJUDGE", ""),
                    help="re-score a saved ragops-<ts>.json instead of running the suite")
    ap.add_argument("--only", default=env("ONLY", ""), help="comma-separated golden ids (debugging)")
    args = ap.parse_args(argv)
    args.judge_key = env("LLM_API_KEY", "")

    if args.rejudge:
        return rejudge(Path(args.rejudge), args)
    golden = load_golden(Path(args.golden))
    if args.only:
        golden = [q for q in golden if q["id"] in set(args.only.split(","))]
    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    runs = [one_run(args, golden, i + 1) for i in range(args.runs)]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    result = {"timestamp": stamp, "api": args.api, "embed_model": args.embed_model,
              "judge_model": args.judge_model if args.judge_key else None, "seed": args.seed,
              "golden": {"file": Path(args.golden).name, "questions": len(golden),
                         "answerable": sum(q["answerable"] for q in golden),
                         "unanswerable": sum(not q["answerable"] for q in golden),
                         "hard": sum(bool(q["hard"]) for q in golden),
                         "human": sum(q["origin"] == "human" for q in golden),
                         "synthetic": sum(q["origin"] == "synthetic" for q in golden)},
              "collection": None, "runs": runs,
              "seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 1)}
    first = runs[0]["answers"][0]["trace_id"] if runs and runs[0]["answers"] else None
    if first and args.traces:
        rec = find_trace(Path(args.traces), first, 0) or {}
        result["collection"] = rec.get("collection")
        result["embedding_version"] = (rec.get("embedding") or {}).get("version")
    summary = table(runs)
    (out / f"ragops-{stamp}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False),
                                              encoding="utf-8")
    (out / f"ragops-{stamp}.md").write_text(
        f"# RAHBAR offline suite {stamp}\n\ncollection: {result['collection']}\n"
        f"golden: {result['golden']}\n\n{summary}", encoding="utf-8")
    with (out / f"judge-hand-labels-{stamp}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "trace_id", "question", "answer", "judge_supported", "human_label"])
        for r in [r for r in runs[0]["answers"] if r.get("judge")][:12]:
            w.writerow([r["id"], r["trace_id"], r["question"], r["answer"],
                        r["judge"]["supported"], ""])
    print(f"\n=== RAHBAR offline suite  {stamp}  collection={result['collection']} ===")
    print(f"golden: {result['golden']}")
    print(summary)
    print(f"wrote {out / ('ragops-' + stamp + '.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
