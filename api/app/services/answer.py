"""Turns a question into an AskResponse: the eight steps of section 3.2.

1 validate (Pydantic, in the route)  2 cache check  3 embed  4 retrieve (+ superseded
filter)  4b retrieval rail (Assignment 03, D4)  5 augment  6 generate  7 validate, retry
once, fall back  8 store turn + cache  9 write one trace record (Assignment 03, D1).

Each rule lives in its own module so it can be unit-tested: grounding.py (relevance
floor, citation guard, follow-ups), cache.py (semantic cache), rails.py (injection rail),
trace.py (the trace record), providers/llm/base.py (schema validation and the retry).
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from ..config import Settings
from ..logjson import request_id_var
from ..providers.llm.base import GenerationError, LLMProvider
from ..providers.llm.prompt import PROMPT_VERSION, build_messages
from ..retrieval.base import Retriever
from ..retrieval.chroma import wants_older_version
from ..routes import metrics as m
from ..schemas import Answer, AskResponse, Passage, RetrievedRef
from . import rails
from .cache import SemanticCache
from .grounding import (
    FALLBACK_TEXT,
    UNGROUNDED_TEXT,
    abstention,
    below_floor,
    is_followup,
    valid_citations,
)
from .trace import TraceWriter, passage_record, prompt_hash

log = logging.getLogger("rahbar.answer")


def _refs(passages: list[Passage]) -> list[RetrievedRef]:
    return [RetrievedRef(chunk_id=p.chunk_id, source=p.source, section=p.section, page=p.page,
                         score=p.score, doc_version=p.doc_version, doc_id=p.doc_id)
            for p in passages]


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 1)


def _generate(question: str, passages: list[Passage], provider: LLMProvider
              ) -> tuple[Answer, str | None, dict[str, int]]:
    """Call the model. Returns (answer, fallback_reason or None, usage)."""
    started = time.perf_counter()
    try:
        answer = provider.generate(question, passages)
        reason = None
    except GenerationError as exc:
        log.warning("generation failed, serving fallback", extra={"error": str(exc)[:300]})
        answer, reason = abstention("fallback", FALLBACK_TEXT), "invalid_output"
    except Exception as exc:  # timeout, provider down: still never a 500
        log.error("provider error, serving fallback",
                  extra={"error": f"{type(exc).__name__}: {str(exc)[:200]}"})
        answer, reason = abstention("fallback", FALLBACK_TEXT), "provider_error"
    m.GENERATION_SECONDS.observe(time.perf_counter() - started)
    usage = getattr(provider, "last_usage", None)
    tokens = {"in": getattr(usage, "tokens_in", 0), "out": getattr(usage, "tokens_out", 0),
              "attempts": getattr(usage, "attempts", 1)}
    return answer, reason, tokens


def _retrieve(retriever: Retriever, question: str, k: int, vector: list[float] | None,
              include_old: bool) -> tuple[list[Passage], dict[str, Any]]:
    traced = getattr(retriever, "retrieve_traced", None)
    if traced is not None:
        return traced(question, k, vector=vector, include_superseded=include_old)
    found = retriever.retrieve(question, k=k, vector=vector, include_superseded=include_old)
    order = [p.chunk_id for p in found]
    return found, {"filters": {"include_superseded": include_old}, "dense_order": order,
                   "reranker": "none", "reranked_order": order,
                   "collection": {"name": getattr(retriever, "name", "?")}}


def _model_params(provider: LLMProvider, settings: Settings) -> dict[str, Any]:
    return {"provider": provider.name,
            "model": settings.llm_model if provider.name != "stub" else "stub",
            "temperature": settings.temperature, "max_tokens": settings.max_tokens,
            "timeout_s": settings.llm_timeout, "response_format": "json_object",
            "prompt_template": PROMPT_VERSION,
            "prompt_rules": os.environ.get("PROMPT_RULES", "on")}


def answer_question(question: str, retriever: Retriever, provider: LLMProvider,
                    settings: Settings, cache: SemanticCache | None = None,
                    index_id: str = "none", tracer: TraceWriter | None = None) -> AskResponse:
    rid = request_id_var.get()
    started = time.perf_counter()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    lat: dict[str, float] = {}
    guardrails: list[dict[str, Any]] = []
    followup = is_followup(question)
    query_event = rails.screen_question(question)
    if query_event:
        guardrails.append(query_event)
        m.INJECTIONS.labels(where="query", action="flagged").inc()

    embed_info = {"model": settings.embed_model,
                  "version": _safe(lambda: getattr(retriever, "embed_model_version")(), "unknown")}

    # 3. Embed once; the vector serves the cache and the retriever.
    t0 = time.perf_counter()
    vector = retriever.embed_query(question)
    lat["embed"] = _ms(time.perf_counter() - t0)

    # 2. Cache check (skipped for follow-ups and when there is no cache or no vector).
    cache_result = "skip"
    t1 = time.perf_counter()
    if cache is not None and vector is not None and not followup:
        try:
            cache.invalidate_except(index_id)
            hit = cache.lookup(index_id, vector)
            cache_result = "hit" if hit else "miss"
            if hit:
                payload, sim = hit
                lat["cache"] = _ms(time.perf_counter() - t1)
                m.record_cache("hit")
                m.RETRIEVAL_SECONDS.observe(time.perf_counter() - t0)
                log.info("answered", extra={"cache": "hit", "similarity": round(sim, 4),
                                            "answered_from_context": True,
                                            "chunk_ids": [r["chunk_id"] for r in
                                                          payload.get("retrieved", [])]})
                response = AskResponse(**{**payload, "request_id": rid, "cached": True,
                                          "trace_id": rid})
                lat["total"] = _ms(time.perf_counter() - started)
                _finish(tracer, {
                    "trace_id": rid, "timestamp": stamp, "user_query": question,
                    "rewritten_query": None, "embedding": embed_info,
                    "collection": {"name": settings.collection, "index_id": index_id},
                    "retrieval": {"top_k": settings.top_k, "from_cache": True,
                                  "cache_similarity": round(sim, 4),
                                  "retrieved": [{"rank": i, **ref} for i, ref in
                                                enumerate(payload.get("retrieved", []), 1)]},
                    "context": None, "prompt": None, "model": None,
                    "response": _response_block(response, None, 0),
                    "citations": [c.model_dump() for c in response.citations],
                    "guardrails": guardrails, "latency_ms": lat, "cache": "hit"},
                    lat, abstained=False)
                return response
        except Exception as exc:  # a broken cache degrades to no cache, never to an error
            log.warning("cache lookup failed", extra={"error": str(exc)[:200]})
            cache_result = "skip"
    lat["cache"] = _ms(time.perf_counter() - t1)
    m.record_cache(cache_result)

    # 4. Retrieve, excluding superseded documents unless the user asked for an old version.
    t2 = time.perf_counter()
    include_old = wants_older_version(question)
    passages, rinfo = _retrieve(retriever, question, settings.top_k, vector, include_old)
    lat["retrieve"] = _ms(time.perf_counter() - t2)
    m.RETRIEVAL_SECONDS.observe(time.perf_counter() - t0)
    if passages:
        m.TOP1_SIMILARITY.observe(max(p.score for p in passages))

    # 4b. Retrieval rail: drop (or flag) chunks that read like instructions to the model.
    t3 = time.perf_counter()
    context, events = rails.screen_passages(passages)
    for ev in events:
        m.INJECTIONS.labels(where="chunk", action=ev["action"]).inc()
    guardrails.extend(events)
    lat["rails"] = _ms(time.perf_counter() - t3)

    fallback_reason: str | None = None
    tokens = {"in": 0, "out": 0, "attempts": 0}
    dropped = 0
    messages_hash: str | None = None
    lat["generate"] = 0.0
    if below_floor(context, settings.relevance_floor):
        # Honest abstention before spending a model call (section 3.4).
        answer = abstention(f"best score below RELEVANCE_FLOOR={settings.relevance_floor}")
        abstain_reason: str | None = "relevance_floor"
        guardrails.append({"rail": "relevance_floor", "threshold": settings.relevance_floor,
                           "top1": max((p.score for p in context), default=None),
                           "action": "abstained before the model call"})
    else:
        # 5-7. Augment, generate, validate (with one retry inside the provider), fall back.
        with_rules = os.environ.get("PROMPT_RULES", "on") != "off"
        messages_hash = prompt_hash(build_messages(question, context, with_rules=with_rules))
        t4 = time.perf_counter()
        answer, fallback_reason, tokens = _generate(question, context, provider)
        lat["generate"] = _ms(time.perf_counter() - t4)
        abstain_reason = "fallback" if fallback_reason else None
        if fallback_reason:
            guardrails.append({"rail": "output_schema", "action": "fallback served",
                               "reason": fallback_reason})
        # The citation guard: every citation must match a chunk retrieved for this request.
        kept, dropped = valid_citations(answer.citations, context)
        if dropped:
            m.CITATIONS_DROPPED.inc(dropped)
            guardrails.append({"rail": "citation_guard", "action": f"dropped {dropped} "
                               "citation(s) that matched no retrieved chunk"})
        answer = answer.model_copy(update={"citations": kept})
        if answer.answered_from_context and not kept:
            answer = abstention("no valid citation", UNGROUNDED_TEXT)
            abstain_reason = "no_valid_citation"
            guardrails.append({"rail": "citation_guard",
                               "action": "abstained: no valid citation left"})
        elif not answer.answered_from_context and not abstain_reason:
            abstain_reason = "model"
            answer = answer.model_copy(update={"citations": []})

    if fallback_reason:
        m.FALLBACKS.labels(reason=fallback_reason).inc()
    if abstain_reason:
        m.ABSTENTIONS.labels(reason=abstain_reason).inc()
    if tokens["in"] or tokens["out"]:
        m.TOKENS_IN.observe(tokens["in"])
        m.TOKENS_OUT.observe(tokens["out"])

    response = AskResponse(
        request_id=rid, answer=answer.answer, citations=answer.citations,
        answered_from_context=answer.answered_from_context, confidence=answer.confidence,
        retrieved=_refs(passages), provider=provider.name, trace_id=rid,
    )

    # One line per request with everything needed to debug stages A-E (section 4.8).
    log.info("answered", extra={
        "retriever": retriever.name, "provider": provider.name, "top_k": settings.top_k,
        "cache": cache_result, "include_superseded": include_old,
        "chunk_ids": [p.chunk_id for p in passages],
        "scores": [round(p.score, 4) for p in passages],
        "answered_from_context": answer.answered_from_context,
        "abstain_reason": abstain_reason, "fallback": fallback_reason,
        "citations": len(answer.citations), "citations_dropped": dropped,
        "tokens_in": tokens["in"], "tokens_out": tokens["out"], "attempts": tokens["attempts"],
    })

    # 8. Store the turn, and a cache entry only when it is safe to share with everyone.
    t5 = time.perf_counter()
    if cache is not None:
        _store(cache, index_id, vector, question, response, followup, abstain_reason, rid)
    lat["cache_store"] = _ms(time.perf_counter() - t5)
    lat["total"] = _ms(time.perf_counter() - started)

    # 9. The trace record (D1).
    _finish(tracer, {
        "trace_id": rid, "timestamp": stamp, "user_query": question,
        # RAHBAR does not rewrite queries; the exact terms it searches for lexically are
        # under retrieval.filters.lexical_terms.
        "rewritten_query": None,
        "embedding": embed_info,
        "collection": rinfo.get("collection"),
        "retrieval": {"top_k": settings.top_k, "hybrid": settings.hybrid,
                      "filters": rinfo.get("filters"),
                      "dense_order": rinfo.get("dense_order"),
                      "reranker": rinfo.get("reranker"),
                      "reranked_order": rinfo.get("reranked_order"),
                      "retrieved": [passage_record(p, i, with_text=False)
                                    for i, p in enumerate(passages, start=1)]},
        "context": [passage_record(p, i, with_text=True) for i, p in enumerate(context, 1)],
        "prompt": {"hash": messages_hash, "template": PROMPT_VERSION,
                   "rules": os.environ.get("PROMPT_RULES", "on")} if messages_hash else None,
        "model": {**_model_params(provider, settings), "attempts": tokens["attempts"],
                  "tokens_in": tokens["in"], "tokens_out": tokens["out"]}
                 if messages_hash else None,
        "grounding": {"relevance_floor": settings.relevance_floor,
                      "top1_score": max((p.score for p in passages), default=None),
                      "abstain_reason": abstain_reason, "fallback": fallback_reason,
                      "citations_dropped": dropped},
        "response": _response_block(response, abstain_reason, dropped),
        "citations": [c.model_dump() for c in response.citations],
        "guardrails": guardrails, "latency_ms": lat, "cache": cache_result,
    }, lat, abstained=not response.answered_from_context)
    return response


def _response_block(r: AskResponse, abstain_reason: str | None, dropped: int) -> dict:
    return {"answer": r.answer, "answered_from_context": r.answered_from_context,
            "confidence": r.confidence, "abstain_reason": abstain_reason}


def _finish(tracer: TraceWriter | None, record: dict[str, Any], lat: dict[str, float],
            abstained: bool) -> None:
    for stage, ms in lat.items():
        m.STAGE_SECONDS.labels(stage=stage).observe(ms / 1000)
    m.record_answer(abstained)
    if tracer is not None:
        try:
            tracer.write(record)
        except Exception as exc:     # tracing must never fail an answer
            log.warning("trace write failed", extra={"error": str(exc)[:200]})


def _safe(fn: Any, default: str) -> str:
    try:
        return str(fn())
    except Exception:
        return default


def _store(cache: SemanticCache, index_id: str, vector: list[float] | None, question: str,
           response: AskResponse, followup: bool, abstain_reason: str | None, rid: str) -> None:
    never_cache = (followup or vector is None or abstain_reason is not None
                   or not response.answered_from_context or not response.citations)
    try:
        cache.record_turn({"request_id": rid, "ts": int(time.time()), "question": question,
                           "answered_from_context": response.answered_from_context,
                           "chunk_ids": [r.chunk_id for r in response.retrieved]})
        if not never_cache and vector is not None:
            payload: dict[str, Any] = response.model_dump()
            payload.pop("request_id", None)
            payload.pop("trace_id", None)
            cache.store(index_id, vector, question, payload)
    except Exception as exc:
        log.warning("cache store failed", extra={"error": str(exc)[:200]})
