"""D1 / F4: one trace record per query, as one JSON line.

Every record goes to standard output (so `kubectl logs` shows it, marked
"logger": "rahbar.trace") and is appended to TRACE_DIR/traces-<pod>.jsonl on the traces
PersistentVolumeClaim, where the report scripts read it. One file per pod: three api
replicas never interleave half-lines in one file.

The record holds the exact context (every chunk's text and metadata, in the order the
model saw it) and a SHA-256 of the exact messages sent to the model. The trace tool
(app/tools/trace_show.py) rebuilds the prompt from the context and checks it against
that hash, so "this is the prompt that produced this answer" is verified, not assumed.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import threading
from pathlib import Path
from typing import Any

from ..schemas import Passage

TRACE_SCHEMA = "rahbar.trace/v1"
_lock = threading.Lock()


def prompt_hash(messages: list[dict[str, str]]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def passage_record(p: Passage, rank: int, with_text: bool) -> dict[str, Any]:
    rec: dict[str, Any] = {"rank": rank, "chunk_id": p.chunk_id, "doc_id": p.doc_id,
                           "source": p.source, "section": p.section, "page": p.page,
                           "doc_version": p.doc_version, "superseded": p.superseded,
                           "score": p.score}
    if with_text:
        rec["text"] = p.text
    return rec


class TraceWriter:
    def __init__(self, trace_dir: str | None = None, to_stdout: bool = True) -> None:
        self.to_stdout = to_stdout
        self.path: Path | None = None
        if trace_dir:
            pod = os.environ.get("HOSTNAME") or socket.gethostname()
            directory = Path(trace_dir)
            try:
                directory.mkdir(parents=True, exist_ok=True)
                self.path = directory / f"traces-{pod}.jsonl"
            except OSError:
                self.path = None             # stdout still has every record

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps({"logger": "rahbar.trace", "schema": TRACE_SCHEMA, **record},
                          ensure_ascii=False, default=str)
        with _lock:
            if self.to_stdout:
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
            if self.path is not None:
                try:
                    with self.path.open("a", encoding="utf-8") as fh:
                        fh.write(line + "\n")
                except OSError:
                    pass                     # a full volume must never fail an answer


def make_writer() -> TraceWriter:
    return TraceWriter(os.environ.get("TRACE_DIR") or None,
                       to_stdout=os.environ.get("TRACE_STDOUT", "true").lower() != "false")
