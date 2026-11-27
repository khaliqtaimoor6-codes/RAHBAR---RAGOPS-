#!/usr/bin/env python3
"""Part E1: send the live query log through /api/ask and keep answers plus trace ids.

    python eval/live_queries.py --api http://rahbar.local --out eval/results/live

Every /api/ask call writes a trace in the api pods, so the JSON written here is only an
index into the real live query log (traces/). Cache is bypassed so each query is answered
fresh. Exit 1 if any query failed, so an incomplete log is never accepted as evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

HERE = Path(__file__).resolve().parent


def load_queries(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        for key in ("id", "query", "topic", "in_domain"):
            if key not in row:
                raise ValueError(f"{path}: query {row.get('id')!r} is missing {key!r}")
    return rows


def ask(client: Any, api: str, question: str, retries: int = 4) -> dict[str, Any]:
    url = api.rstrip("/") + "/api/ask"
    for attempt in range(retries):
        try:
            response = client.post(url, json={"question": question},
                                   headers={"X-RAHBAR-Cache": "bypass"})
            if response.status_code == 429:
                wait = min(float(response.headers.get("retry-after", "2") or 2), 10)
                time.sleep(wait + attempt)
                continue
            if response.status_code >= 500 and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def run(args: argparse.Namespace, client: Any = None) -> dict[str, Any]:
    queries = load_queries(Path(args.queries))
    if args.limit:
        queries = queries[:args.limit]
    client = client or httpx.Client(timeout=120)
    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    rows: list[dict[str, Any]] = []
    for question in queries:
        t0 = time.perf_counter()
        row: dict[str, Any] = {
            "id": question["id"], "topic": question["topic"],
            "in_domain": question["in_domain"], "query": question["query"],
        }
        try:
            response = ask(client, args.api, question["query"])
            retrieved = response.get("retrieved") or []
            row.update({
                "trace_id": response.get("trace_id"),
                "answered": response.get("answered_from_context"),
                "answer": response.get("answer"),
                "citations": response.get("citations"),
                "top_score": max((r.get("score") or 0 for r in retrieved), default=None),
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "cached": response.get("cached"),
                "error": None,
            })
            print(f"  {row['id']:>3} {row['latency_ms']:>8.1f}ms "
                  f"answered={row['answered']} trace={row['trace_id']}", flush=True)
        except Exception as exc:
            row.update({
                "trace_id": None, "answer": None, "answered": None,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": f"{type(exc).__name__}: {exc}",
            })
            print(f"  {row['id']:>3} ERROR {row['error']}", flush=True)
        rows.append(row)
        time.sleep(args.pace)

    result = {
        "timestamp": stamp, "api": args.api, "queries_file": Path(args.queries).name,
        "questions": len(rows),
        "in_domain": sum(bool(r["in_domain"]) for r in rows),
        "off_topic": sum(not r["in_domain"] for r in rows),
        "errors": sum(bool(r.get("error")) for r in rows),
        "seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
        "results": rows,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"live-{stamp}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False),
                                           encoding="utf-8")
    lines = [f"# RAHBAR live queries {stamp}", "",
             f"{result['questions']} queries ({result['in_domain']} in-domain, "
             f"{result['off_topic']} off-topic), {result['errors']} errors", "",
             "| id | topic | answered | top score | ms | trace |", "|---|---|---|---:|---:|---|"]
    for row in rows:
        lines.append(f"| {row['id']} | {row['topic']} | {row.get('answered')} | "
                     f"{row.get('top_score')} | {row['latency_ms']} | {row.get('trace_id')} |")
    (out / f"live-{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out / ('live-' + stamp + '.json')}")
    return result


def main(argv: list[str] | None = None) -> int:
    env = os.environ.get
    ap = argparse.ArgumentParser(description="RAHBAR live query log (Part E1).")
    ap.add_argument("--api", default=env("API_URL", "http://localhost:8000"))
    ap.add_argument("--queries", default=env("LIVE_QUERIES", str(HERE / "live_queries.jsonl")))
    ap.add_argument("--out", default=env("RESULTS_DIR", str(HERE / "results/live")))
    ap.add_argument("--pace", type=float, default=float(env("PACE_SECONDS", "2")),
                    help="seconds between calls (free-tier rate limits)")
    ap.add_argument("--limit", type=int, default=0, help="first N queries (development only)")
    args = ap.parse_args(argv)
    result = run(args)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
