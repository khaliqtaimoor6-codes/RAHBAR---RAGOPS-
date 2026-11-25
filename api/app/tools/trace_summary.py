"""D3: summarise the trace log over a time window.

    kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_summary --since 60m
    python -m app.tools.trace_summary --traces ../traces --since 24h --out ../eval/results/x.json

Reports, for the traces in the window:
  * top-1 retrieval similarity: min / p10 / p50 / p90 / max and a histogram
  * abstention rate (and by reason)
  * cache hit rate (hits / (hits + misses); 'skip' = not eligible, not counted)
  * p50 and p95 latency per stage (embed, cache, retrieve, rails, generate, total)
  * prompt-injection attempts flagged (chunks dropped/flagged, queries flagged)
The /metrics endpoint exposes the same quantities live (rahbar_top1_similarity,
rahbar_abstention_rate, rahbar_cache_hit_ratio, rahbar_stage_seconds,
rahbar_injection_flagged_total); this script is the after-the-fact view.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .trace_show import default_paths, iter_records

BUCKETS = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 1.01)


def parse_window(text: str) -> timedelta:
    m = re.fullmatch(r"(\d+)([smhd])", text.strip())
    if not m:
        raise argparse.ArgumentTypeError("use e.g. 30m, 6h, 7d")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(**{{"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}[unit]: n})


def ts(rec: dict[str, Any]) -> datetime:
    return datetime.strptime(rec["timestamp"][:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=timezone.utc)


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 4)


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    top1 = [r["grounding"]["top1_score"] for r in records
            if (r.get("grounding") or {}).get("top1_score") is not None]
    hist = Counter()
    for v in top1:
        lo = 0.0
        for b in BUCKETS:
            if v < b:
                hist[f"[{lo:.2f},{min(b, 1.0):.2f})"] += 1
                break
            lo = b
    abstained = [r for r in records if not (r.get("response") or {}).get("answered_from_context")]
    reasons = Counter((r.get("response") or {}).get("abstain_reason") or "unknown"
                      for r in abstained)
    cache = Counter(r.get("cache") for r in records)
    stages: dict[str, list[float]] = {}
    for r in records:
        for stage, ms in (r.get("latency_ms") or {}).items():
            stages.setdefault(stage, []).append(float(ms))
    inj = Counter()
    for r in records:
        for g in r.get("guardrails") or []:
            if g.get("rail") in ("retrieval_injection", "query_injection"):
                inj[f"{g['rail']}:{str(g.get('action')).split(' ')[0]}"] += 1
    inj_traces = sum(1 for r in records if any(
        g.get("rail") in ("retrieval_injection", "query_injection")
        for g in r.get("guardrails") or []))
    hits, misses = cache.get("hit", 0), cache.get("miss", 0)
    return {
        "traces": n,
        "window": {"first": records[0]["timestamp"] if records else None,
                   "last": records[-1]["timestamp"] if records else None},
        "top1_similarity": {"n": len(top1), "min": pct(top1, 0), "p10": pct(top1, .1),
                            "p50": pct(top1, .5), "p90": pct(top1, .9), "max": pct(top1, 1),
                            "histogram": dict(sorted(hist.items()))},
        "abstention_rate": round(len(abstained) / n, 4) if n else None,
        "abstentions_by_reason": dict(reasons),
        "cache": {"hit": hits, "miss": misses, "skip": cache.get("skip", 0),
                  "hit_rate": round(hits / (hits + misses), 4) if hits + misses else None},
        "latency_ms": {s: {"p50": pct(v, .5), "p95": pct(v, .95), "n": len(v)}
                       for s, v in sorted(stages.items())},
        "injection": {"traces_with_injection": inj_traces, "events": dict(inj)},
        "collections": dict(Counter(f"{(r.get('collection') or {}).get('name')}@"
                                    f"{(r.get('collection') or {}).get('index_id')}"
                                    for r in records)),
        "embedding_versions": dict(Counter((r.get("embedding") or {}).get("version")
                                           for r in records)),
    }


def print_table(s: dict[str, Any]) -> None:
    print(f"traces: {s['traces']}   window: {s['window']['first']} .. {s['window']['last']}")
    t = s["top1_similarity"]
    print(f"\ntop-1 similarity   n={t['n']}  min={t['min']}  p10={t['p10']}  p50={t['p50']}  "
          f"p90={t['p90']}  max={t['max']}")
    for bucket, count in t["histogram"].items():
        print(f"  {bucket:14} {'#' * count} {count}")
    print(f"\nabstention rate    {s['abstention_rate']}   by reason: "
          f"{s['abstentions_by_reason']}")
    c = s["cache"]
    print(f"cache hit rate     {c['hit_rate']}   (hit={c['hit']} miss={c['miss']} "
          f"skip={c['skip']})")
    print(f"injection flagged  {s['injection']['traces_with_injection']} trace(s)   "
          f"{s['injection']['events']}")
    print(f"\n{'stage':14} {'p50 ms':>10} {'p95 ms':>10} {'n':>6}")
    for stage, v in s["latency_ms"].items():
        print(f"{stage:14} {v['p50']!s:>10} {v['p95']!s:>10} {v['n']:>6}")
    print(f"\ncollections:        {s['collections']}")
    print(f"embedding versions: {s['embedding_versions']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Summarise trace records over a time window.")
    ap.add_argument("--traces", action="append", type=Path)
    ap.add_argument("--since", type=parse_window, help="e.g. 30m, 6h, 7d (default: all)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    ap.add_argument("--out", type=Path, help="also write the JSON summary to this file")
    args = ap.parse_args(argv)
    records = sorted(iter_records(args.traces or default_paths()), key=ts)
    seen: set[str] = set()
    unique = []
    for r in records:                # the same trace may be in a file and in kubectl logs
        if r["trace_id"] not in seen:
            seen.add(r["trace_id"])
            unique.append(r)
    if args.since:
        cutoff = datetime.now(timezone.utc) - args.since
        unique = [r for r in unique if ts(r) >= cutoff]
    s = summarise(unique)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(s, indent=1), encoding="utf-8")
    if args.json:
        print(json.dumps(s, indent=1))
    else:
        print_table(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
