"""D2: the trace tool. Takes a trace id, prints the exact context and the exact prompt
that produced that answer, and proves it: the prompt is rebuilt from the recorded context
with the same template and its SHA-256 is compared with the hash recorded at answer time.

On the cluster (the api image has the tool and the traces volume):
    kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show <trace_id>
Locally, against traces copied out of the cluster:
    python -m app.tools.trace_show <trace_id> --traces ../traces       (from api/)

Options: --json prints the raw record; --messages prints the messages as JSON.
Exit code 0 = found and the hash matches; 1 = not found; 2 = found but the rebuilt prompt
does not match (the template changed since: see prompt.template in the record).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterator

from ..providers.llm.prompt import PROMPT_VERSION, build_messages
from ..schemas import Passage
from ..services.trace import prompt_hash


def iter_records(paths: list[Path]) -> Iterator[dict[str, Any]]:
    """Every trace record in the given files or directories. Lines from `kubectl logs`
    work too: anything that is not a JSON trace line is skipped."""
    files: list[Path] = []
    for p in paths:
        files.extend(sorted(p.rglob("*.jsonl")) + sorted(p.rglob("*.log")) if p.is_dir()
                     else [p])
    for f in files:
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("{") or '"rahbar.trace"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("logger") == "rahbar.trace":
                    yield rec


def find(trace_id: str, paths: list[Path]) -> dict[str, Any] | None:
    hit = None
    for rec in iter_records(paths):
        if rec.get("trace_id") == trace_id or rec.get("trace_id", "").startswith(trace_id):
            hit = rec
    return hit


def rebuild(rec: dict[str, Any]) -> list[dict[str, str]]:
    passages = [Passage(chunk_id=c["chunk_id"], text=c["text"], source=c["source"],
                        section=c["section"], page=c.get("page"), score=c.get("score", 0.0),
                        doc_version=c.get("doc_version"),
                        superseded=bool(c.get("superseded", False)), doc_id=c.get("doc_id"))
                for c in rec.get("context") or []]
    with_rules = (rec.get("prompt") or {}).get("rules", "on") != "off"
    return build_messages(rec["user_query"], passages, with_rules=with_rules)


def default_paths() -> list[Path]:
    return [Path(os.environ.get("TRACE_DIR") or "traces")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rebuild the exact prompt behind a trace id.")
    ap.add_argument("trace_id", help="the trace id (= request id); a unique prefix works")
    ap.add_argument("--traces", action="append", type=Path,
                    help="trace file or directory (repeatable); default $TRACE_DIR")
    ap.add_argument("--json", action="store_true", help="print the raw record")
    ap.add_argument("--messages", action="store_true", help="print the messages as JSON")
    args = ap.parse_args(argv)
    rec = find(args.trace_id, args.traces or default_paths())
    if rec is None:
        print(f"trace {args.trace_id} not found", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(rec, indent=1, ensure_ascii=False))
        return 0

    bar = "=" * 78
    col = rec.get("collection") or {}
    emb = rec.get("embedding") or {}
    model = rec.get("model") or {}
    print(bar)
    print(f"trace {rec['trace_id']}   {rec.get('timestamp')}   cache={rec.get('cache')}")
    print(f"query:       {rec['user_query']}")
    print(f"collection:  {col.get('name')}  index_id={col.get('index_id')}  "
          f"indexed_at={col.get('indexed_at')}")
    print(f"embedding:   {emb.get('model')}  version={emb.get('version')}")
    if model:
        print(f"model:       {model.get('provider')}/{model.get('model')}  "
              f"temperature={model.get('temperature')}  max_tokens={model.get('max_tokens')}  "
              f"attempts={model.get('attempts')}")
    filters = (rec.get("retrieval") or {}).get("filters")
    print(f"filters:     {json.dumps(filters)}")
    for g in rec.get("guardrails") or []:
        print(f"guardrail:   {json.dumps(g, ensure_ascii=False)}")

    print(f"\n{bar}\nRETRIEVED (before rails; reranked order)\n{bar}")
    for i, r in enumerate((rec.get("retrieval") or {}).get("retrieved") or [], start=1):
        print(f"  #{r.get('rank', i)} {r['score']:.4f}  {r['chunk_id']}  doc={r.get('doc_id')} "
              f"v={r.get('doc_version')} superseded={r.get('superseded')}")

    context = rec.get("context")
    if context is None:
        print("\n(answered from the semantic cache: no prompt was built for this request)")
        return 0
    print(f"\n{bar}\nCONTEXT SENT TO THE MODEL ({len(context)} chunk(s))\n{bar}")
    for c in context:
        print(f"--- [{c['rank']}] {c['chunk_id']}  {c['source']} | {c['section']} | "
              f"p.{c.get('page')} | v{c.get('doc_version')} | score {c.get('score')}")
        print(c["text"])

    if not rec.get("prompt"):
        print(f"\n(no model call: {(rec.get('grounding') or {}).get('abstain_reason')})")
        print(f"\nRESPONSE: {(rec.get('response') or {}).get('answer')}")
        return 0
    messages = rebuild(rec)
    rebuilt = prompt_hash(messages)
    recorded = rec["prompt"]["hash"]
    print(f"\n{bar}\nPROMPT (rebuilt with template {PROMPT_VERSION}; "
          f"recorded template {rec['prompt'].get('template')})\n{bar}")
    if args.messages:
        print(json.dumps(messages, indent=1, ensure_ascii=False))
    else:
        for msg in messages:
            print(f"<<< {msg['role']} >>>\n{msg['content']}\n")
    ok = rebuilt == recorded
    print(f"{bar}\nprompt hash recorded: {recorded}\nprompt hash rebuilt:  {rebuilt}\n"
          f"{'MATCH: this is exactly the prompt that produced the answer' if ok else 'MISMATCH'}")
    print(f"\nRESPONSE: {(rec.get('response') or {}).get('answer')}")
    print(f"CITATIONS: {json.dumps(rec.get('citations'), ensure_ascii=False)}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
