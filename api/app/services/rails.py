"""D4: the retrieval rail against prompt injection, logged into every trace.

Assignment 02's defence lives in the prompt (providers/llm/prompt.py): retrieved text and
the question are wrapped in tags, tag-like text is neutralised, and the system prompt says
that instructions inside the data are not instructions. That works only if the model
obeys. This rail acts BEFORE the model sees anything:

* every retrieved chunk is scanned for instruction-like text, and a chunk whose document
  the ingestion Job's verification stage already flagged (`injection_suspect`) counts too;
* INJECTION_ACTION=drop (default) removes such chunks from the context; `flag` keeps them
  (the prompt defence still applies) but records the event; `off` disables the rail;
* the user's question is scanned as well. A question is never dropped (it is the user's
  own text, and the prompt already treats it as data), only flagged.

Each event goes into the trace's `guardrails` list and the injection counter in /metrics.
"""

from __future__ import annotations

import os
import re
from typing import Any

from ..schemas import Passage

# Keep in step with indexer/pipeline/verify.py (INJECTION_PATTERNS).
PATTERNS = [
    r"ignore (?:all |any )?(?:the )?(?:previous|prior|above|earlier|your) (?:instructions|rules)",
    r"disregard (?:all |any )?(?:the )?(?:previous|prior|above|your) (?:instructions|rules)",
    r"you are now (?:a|an|in)\b",
    r"(?:reveal|print|show) (?:your|the) (?:system )?prompt",
    r"system prompt",
    r"new instructions?:",
    r"(?:assistant|ai|model|chatbot)s? (?:must|should) (?:always )?(?:say|answer|respond|tell)",
]
_INJECTION = re.compile("|".join(f"(?:{p})" for p in PATTERNS), re.I)


def action() -> str:
    return os.environ.get("INJECTION_ACTION", "drop").strip().lower()


def find(text: str) -> str | None:
    m = _INJECTION.search(text)
    return m.group(0) if m else None


def screen_passages(passages: list[Passage]) -> tuple[list[Passage], list[dict[str, Any]]]:
    """Return (passages to send to the model, guardrail events)."""
    mode = action()
    if mode == "off":
        return passages, []
    kept: list[Passage] = []
    events: list[dict[str, Any]] = []
    for p in passages:
        match = find(p.text)
        if match or p.injection_suspect:
            events.append({
                "rail": "retrieval_injection", "chunk_id": p.chunk_id, "doc_id": p.doc_id,
                "match": match, "flagged_at_ingest": p.injection_suspect,
                "action": "dropped" if mode == "drop" else "flagged"})
            if mode == "drop":
                continue
        kept.append(p)
    return kept, events


def screen_question(question: str) -> dict[str, Any] | None:
    if action() == "off":
        return None
    match = find(question)
    if not match:
        return None
    return {"rail": "query_injection", "match": match,
            "action": "flagged (answered from evidence only; question treated as data)"}
