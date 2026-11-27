#!/usr/bin/env python3
"""Part E2/E4: how much of the live query log is covered by the golden set?

For every live query, embed it and every golden question with nomic-embed-text
(`search_query: ` prefix), take the most similar golden question, and report the share
above `--threshold`. Off-topic queries are expected to sit below it; the gate is the
in-domain share, which must reach `--min-share` or the script exits 1. Uncovered in-domain
queries are listed by topic so E4 can add questions where the gap actually is.

    python eval/coverage.py --live eval/results/live/live-<ts>.json \
        --golden eval/golden.jsonl --out eval/results/coverage
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ragops_suite import QUERY_PREFIX, Embedder, cosine, mean

HERE = Path(__file__).resolve().parent


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_live(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["results"] if isinstance(data, dict) and "results" in data else data


def run(args: argparse.Namespace, embedder: Any = None) -> dict[str, Any]:
    golden = load_jsonl(Path(args.golden))
    live = load_live(Path(args.live))
    emb = embedder or Embedder(args.ollama, args.embed_model)
    prefix = QUERY_PREFIX.get(args.embed_model.split(":")[0], "")
    golden_vectors = emb.embed([q["question"] for q in golden], prefix)
    live_vectors = emb.embed([r["query"] for r in live], prefix)

    rows: list[dict[str, Any]] = []
    for query, vector in zip(live, live_vectors):
        scores = [cosine(vector, gv) for gv in golden_vectors]
        best = max(range(len(scores)), key=scores.__getitem__)
        rows.append({
            "id": query["id"], "topic": query["topic"], "in_domain": bool(query["in_domain"]),
            "query": query["query"], "best_golden": golden[best]["id"],
            "score": round(scores[best], 4), "covered": scores[best] >= args.threshold,
        })

    in_domain = [r for r in rows if r["in_domain"]]
    off_topic = [r for r in rows if not r["in_domain"]]
    share_in = mean([1.0 if r["covered"] else 0.0 for r in in_domain]) or 0.0
    share_off = mean([1.0 if r["covered"] else 0.0 for r in off_topic]) or 0.0
    uncovered = [r for r in in_domain if not r["covered"]]
    by_topic: dict[str, list[str]] = defaultdict(list)
    for r in uncovered:
        by_topic[r["topic"]].append(r["id"])

    result = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "golden": str(args.golden), "golden_questions": len(golden),
        "live": str(args.live), "live_queries": len(rows),
        "in_domain": len(in_domain), "off_topic": len(off_topic),
        "cosine_threshold": args.threshold, "required_share": args.min_share,
        "in_domain_share": share_in, "off_topic_share": share_off,
        "covered_in_domain": sum(bool(r["covered"]) for r in in_domain),
        "score_stats": {
            "in_domain_min": min((r["score"] for r in in_domain), default=None),
            "in_domain_mean": mean([r["score"] for r in in_domain]),
            "in_domain_max": max((r["score"] for r in in_domain), default=None),
            "off_topic_min": min((r["score"] for r in off_topic), default=None),
            "off_topic_mean": mean([r["score"] for r in off_topic]),
            "off_topic_max": max((r["score"] for r in off_topic), default=None),
        },
        "uncovered_by_topic": dict(sorted(by_topic.items())),
        "uncovered": uncovered, "rows": rows,
        "passed": share_in >= args.min_share,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "coverage.json").write_text(json.dumps(result, indent=1, ensure_ascii=False),
                                       encoding="utf-8")
    verdict = "PASS" if result["passed"] else "FAIL"
    lines = [
        f"# RAHBAR live-query coverage: {verdict}", "",
        f"- golden: `{args.golden}` ({len(golden)} questions)",
        f"- live: `{args.live}` ({len(rows)} queries: {len(in_domain)} in-domain, "
        f"{len(off_topic)} off-topic)",
        f"- cosine threshold: {args.threshold}; required in-domain share: {args.min_share}",
        f"- in-domain covered: {result['covered_in_domain']}/{len(in_domain)} = **{share_in}**",
        f"- off-topic covered: {share_off} (expected to be low)",
        f"- score stats: {result['score_stats']}", "",
        "## Uncovered in-domain queries by topic", "",
        "| topic | ids |", "|---|---|",
    ]
    for topic, ids in result["uncovered_by_topic"].items():
        lines.append(f"| {topic} | {', '.join(ids)} |")
    lines += ["", "| id | query | best golden | score |", "|---|---|---|---:|"]
    for r in uncovered:
        lines.append(f"| {r['id']} | {r['query']} | {r['best_golden']} | {r['score']} |")
    (out / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    env = os.environ.get
    ap = argparse.ArgumentParser(description="RAHBAR live-query coverage (Part E2).")
    ap.add_argument("--live", default=env("LIVE_RESULTS", str(HERE / "results/live/live.json")))
    ap.add_argument("--golden", default=env("GOLDEN", str(HERE / "golden.jsonl")))
    ap.add_argument("--ollama", default=env("OLLAMA_URL", "http://localhost:11434"))
    ap.add_argument("--embed-model", default=env("EMBED_MODEL", "nomic-embed-text"))
    ap.add_argument("--threshold", type=float, default=float(env("COVERAGE_THRESHOLD", "0.70")),
                    help="cosine at or above which a live query counts as covered")
    ap.add_argument("--min-share", type=float, default=float(env("MIN_COVERAGE", "0.85")),
                    help="required share of in-domain queries covered; exit 1 below it")
    ap.add_argument("--out", default=env("COVERAGE_OUT", str(HERE / "results/coverage")))
    args = ap.parse_args(argv)
    result = run(args)
    print(f"coverage: in-domain {result['in_domain_share']} "
          f"({result['covered_in_domain']}/{result['in_domain']}), "
          f"off-topic {result['off_topic_share']}; "
          f"{'PASS' if result['passed'] else 'FAIL'}")
    print(f"wrote {Path(args.out) / 'coverage.json'}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
