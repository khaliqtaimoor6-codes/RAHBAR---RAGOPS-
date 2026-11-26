"""POST /api/ask and POST /api/retrieve. The Ingress sends /api/* here unchanged.

/api/ask: the full pipeline. `X-RAHBAR-Cache: bypass` skips the semantic cache for that
request (no lookup, no store). The evaluation suite sends it so a second run measures the
pipeline again instead of replaying the first run from the cache (Part B, stochasticity).

/api/retrieve (Assignment 03, Part B component level): retrieval only, read-only, no model
call and no trace. Same embedding, filters and fusion as /api/ask, so retrieval metrics
and the typo noise test cost no LLM tokens.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..logjson import request_id_var
from ..retrieval.chroma import wants_older_version
from ..schemas import AskRequest, AskResponse
from ..services.answer import _refs, _retrieve, answer_question

router = APIRouter(prefix="/api")
log = logging.getLogger("rahbar.ask")


def _unavailable(exc: Exception) -> JSONResponse:
    # Retrieval itself failed (Chroma or the embedder is down). Readiness will pull this
    # pod out of the Service shortly; until then answer with a clear 503.
    log.error("retrieval unavailable", extra={"error": f"{type(exc).__name__}: {exc}"[:300]})
    return JSONResponse(status_code=503, content={
        "detail": "The document index is temporarily unavailable. Please try again.",
        "request_id": request_id_var.get()})


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request) -> AskResponse | JSONResponse:
    state = request.app.state
    bypass = request.headers.get("X-RAHBAR-Cache", "").lower() == "bypass"
    cache = None if bypass else state.cache
    try:
        index_id = state.retriever.current_index_id() if cache is not None else "none"
        response = answer_question(body.question, state.retriever, state.provider,
                                   state.settings, cache=cache, index_id=index_id,
                                   tracer=getattr(state, "tracer", None))
    except Exception as exc:
        return _unavailable(exc)
    if response.cached:
        return JSONResponse(content=response.model_dump(), headers={"X-Cache": "HIT"})
    return response


@router.post("/retrieve", response_model=None)
def retrieve(body: AskRequest, request: Request) -> dict[str, Any] | JSONResponse:
    state = request.app.state
    try:
        vector = state.retriever.embed_query(body.question)
        include_old = wants_older_version(body.question)
        passages, info = _retrieve(state.retriever, body.question, state.settings.top_k,
                                   vector, include_old)
    except Exception as exc:
        return _unavailable(exc)
    return {"request_id": request_id_var.get(),
            "retrieved": [r.model_dump() for r in _refs(passages)],
            "filters": info.get("filters"), "reranked_order": info.get("reranked_order"),
            "collection": info.get("collection")}
