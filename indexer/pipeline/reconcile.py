"""A2: incremental update of the retrieval sources (RAGOps paper 4.2.4).

The lake registry says which documents should be searchable and in which state; a
Chroma collection is brought in line with it, touching only what differs:

  document unchanged (same file hash, same chunking/embedding config)  -> nothing
  only its state changed (archived <-> current)                         -> metadata update
  document new or changed                                               -> re-chunk; reuse the
        stored vector of every chunk whose text is identical, embed only the rest, then
        replace exactly that document's chunks (delete by doc_id, add)
  document no longer in the lake (deleted, quarantined)                 -> delete its chunks

So re-running on an unchanged corpus embeds 0 chunks, a changed document replaces only
its own chunks, and a deleted document leaves no orphans (`orphans` in the report counts
chunks whose doc_id the lake does not know; it must be 0).

This replaces Assignment 02's build-aside-then-swap for normal runs: a full rebuild is
simply a reconcile into a new, empty collection name (which is also how the Part C
candidate gets its own collection).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from .config import IndexerSettings
from .lake import DocEntry, Lake
from .models import Chunk, Document

WRITE_BATCH = 200
PAGE = 1000

EmbedFn = Callable[[list[str], IndexerSettings], list[list[float]]]


def chunk_config(settings: IndexerSettings) -> str:
    """Anything that changes the chunks or their vectors. A collection built with another
    config is rebuilt document by document."""
    import os

    strategy = os.environ.get("CHUNK_STRATEGY", "structure")
    return f"{settings.embed_model}|{settings.chunk_size}|{settings.chunk_overlap}|{strategy}"


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def chunk_metadata(c: Chunk, e: DocEntry, cfg: str) -> dict[str, Any]:
    meta: dict[str, Any] = dict(c.metadata())
    meta.update({"doc_id": e.doc_id, "family": e.family, "title": e.title[:200],
                 "doc_sha": e.sha256, "text_sha": text_hash(c.text), "chunk_cfg": cfg,
                 "superseded": e.superseded, "doc_version": e.doc_version,
                 "injection_suspect": e.injection_suspect})
    return meta


def _all_rows(col: Any, include: list[str]) -> dict[str, Any]:
    """col.get() in pages, so a large collection is not one giant response."""
    ids: list[str] = []
    metas: list[dict] = []
    offset = 0
    while True:
        res = col.get(include=include, limit=PAGE, offset=offset)
        batch = res.get("ids") or []
        ids.extend(batch)
        metas.extend(res.get("metadatas") or [{}] * len(batch))
        if len(batch) < PAGE:
            return {"ids": ids, "metadatas": metas}
        offset += PAGE


def collection_state(col: Any) -> dict[str, dict[str, Any]]:
    """doc_id -> {ids, doc_sha, cfg, superseded}. Chunks without a doc_id (an Assignment
    02 index) are grouped under '' and treated as orphans to remove."""
    rows = _all_rows(col, ["metadatas"])
    state: dict[str, dict[str, Any]] = defaultdict(lambda: {"ids": [], "doc_sha": None,
                                                            "cfg": None, "superseded": None,
                                                            "injection": None})
    for cid, meta in zip(rows["ids"], rows["metadatas"]):
        meta = meta or {}
        s = state[str(meta.get("doc_id", ""))]
        s["ids"].append(cid)
        s["doc_sha"] = meta.get("doc_sha")
        s["cfg"] = meta.get("chunk_cfg")
        s["superseded"] = meta.get("superseded")
        s["injection"] = meta.get("injection_suspect")
    return dict(state)


def counts_by_doc(col: Any) -> dict[str, int]:
    return {d: len(s["ids"]) for d, s in sorted(collection_state(col).items())}


def open_collection(client: Any, settings: IndexerSettings) -> Any:
    """Get the collection, or create it with the embedding pin. An existing collection
    built with another embedding model is refused: use a new collection name instead."""
    try:
        col = client.get_collection(settings.collection)
    except Exception:
        col = None
    if col is None:
        return client.create_collection(name=settings.collection, metadata={
            "hnsw:space": "cosine", "embed_model": settings.embed_model,
            "index_id": uuid.uuid4().hex[:12], "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap})
    pinned = (col.metadata or {}).get("embed_model")
    if pinned and pinned != settings.embed_model:
        raise SystemExit(f"collection '{settings.collection}' is pinned to embed_model="
                         f"{pinned!r}, this run uses {settings.embed_model!r}: reconcile into "
                         "a new CHROMA_COLLECTION instead (Part C candidate)")
    return col


def _stamp(col: Any, settings: IndexerSettings, dimension: int | None, chunks: int) -> str:
    """New index_id (the API's cache namespace) after any change. Chroma refuses changes
    to hnsw:* keys after creation, so those are left out of the update."""
    meta = {k: v for k, v in (col.metadata or {}).items() if not k.startswith("hnsw:")}
    meta.update({"embed_model": settings.embed_model, "index_id": uuid.uuid4().hex[:12],
                 "indexed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "chunk_size": settings.chunk_size, "chunk_overlap": settings.chunk_overlap,
                 "chunks": chunks})
    if dimension:
        meta["dimension"] = dimension
    col.modify(metadata=meta)
    return str(meta["index_id"])


def _chunks_for(e: DocEntry, doc: Document, settings: IndexerSettings) -> list[Chunk]:
    from .chunk import chunk

    doc.doc_version = e.doc_version
    doc.superseded = e.superseded
    pieces = chunk(doc, settings.chunk_size, settings.chunk_overlap)
    for i, c in enumerate(pieces):        # ids by doc_id: unique across versions and copies
        c.id = f"{e.doc_id}-{i:04d}"
    return pieces


def load_text(lake: Lake, e: DocEntry) -> Document:
    """The cleaned text from the lake's extracted/ cache; extract again only if missing."""
    doc = lake.load_extracted(e.doc_id)
    if doc is None:
        from .clean import clean
        from .extract import extract

        doc = clean(extract(str(lake.root / e.file), e.doc_version, e.superseded))
        lake.save_extracted(e.doc_id, doc)
    return doc


def reconcile(lake: Lake, settings: IndexerSettings, client: Any, embed_fn: EmbedFn,
              log: Callable[..., None] = lambda *a, **k: None) -> dict[str, Any]:
    col = open_collection(client, settings)
    cfg = chunk_config(settings)
    state = collection_state(col)
    desired = lake.docs
    stats: dict[str, Any] = {"collection": settings.collection, "chunk_cfg": cfg,
                             "docs_unchanged": 0, "docs_added": 0, "docs_replaced": 0,
                             "docs_metadata_updated": 0, "docs_removed": 0,
                             "chunks_embedded": 0, "chunks_reused": 0, "chunks_deleted": 0,
                             "chunks_metadata_updated": 0, "per_doc": {}}
    dimension: int | None = (col.metadata or {}).get("dimension")

    # 1. Remove chunks of documents the lake no longer has (deleted, quarantined, or an
    #    old Assignment 02 index without doc_id metadata).
    for doc_id, s in state.items():
        if doc_id not in desired:
            for i in range(0, len(s["ids"]), WRITE_BATCH):
                col.delete(ids=s["ids"][i:i + WRITE_BATCH])
            stats["docs_removed"] += 1
            stats["chunks_deleted"] += len(s["ids"])
            stats["per_doc"][doc_id or "(no doc_id)"] = {"action": "removed",
                                                         "deleted": len(s["ids"])}
            log("removed document chunks", doc_id=doc_id, chunks=len(s["ids"]))

    # 2. Add, replace or re-label the rest.
    for doc_id, e in sorted(desired.items()):
        s = state.get(doc_id)
        if s and s["doc_sha"] == e.sha256 and s["cfg"] == cfg:
            if bool(s["superseded"]) != e.superseded or bool(s["injection"]) != e.injection_suspect:
                got = col.get(ids=s["ids"], include=["metadatas"])
                metas = []
                for m in got["metadatas"]:
                    m = dict(m or {})
                    m["superseded"] = e.superseded
                    m["injection_suspect"] = e.injection_suspect
                    metas.append(m)
                col.update(ids=got["ids"], metadatas=metas)
                stats["docs_metadata_updated"] += 1
                stats["chunks_metadata_updated"] += len(got["ids"])
                stats["per_doc"][doc_id] = {"action": "metadata",
                                            "superseded": e.superseded}
                log("re-labelled document", doc_id=doc_id, superseded=e.superseded,
                    chunks=len(got["ids"]))
            else:
                stats["docs_unchanged"] += 1
            continue

        chunks = _chunks_for(e, load_text(lake, e), settings)
        reuse: dict[str, list[float]] = {}
        if s and s["cfg"] and s["cfg"].split("|")[0] == settings.embed_model:
            old = col.get(ids=s["ids"], include=["embeddings", "metadatas"])
            for vec, meta in zip(old["embeddings"], old["metadatas"]):
                if meta and meta.get("text_sha") is not None:
                    reuse[str(meta["text_sha"])] = [float(x) for x in vec]
        todo = [c for c in chunks if text_hash(c.text) not in reuse]
        fresh = embed_fn([c.text for c in todo], settings) if todo else []
        fresh_by = {text_hash(c.text): v for c, v in zip(todo, fresh)}
        vectors = [reuse.get(text_hash(c.text)) or fresh_by[text_hash(c.text)] for c in chunks]
        if vectors:
            dimension = len(vectors[0])
        if s:
            for i in range(0, len(s["ids"]), WRITE_BATCH):
                col.delete(ids=s["ids"][i:i + WRITE_BATCH])
            stats["chunks_deleted"] += len(s["ids"])
        for i in range(0, len(chunks), WRITE_BATCH):
            part = chunks[i:i + WRITE_BATCH]
            col.add(ids=[c.id for c in part], documents=[c.text for c in part],
                    embeddings=vectors[i:i + WRITE_BATCH],
                    metadatas=[chunk_metadata(c, e, cfg) for c in part])
        stats["docs_replaced" if s else "docs_added"] += 1
        stats["chunks_embedded"] += len(todo)
        stats["chunks_reused"] += len(chunks) - len(todo)
        stats["per_doc"][doc_id] = {"action": "replaced" if s else "added",
                                    "chunks": len(chunks), "embedded": len(todo),
                                    "reused": len(chunks) - len(todo),
                                    "deleted": len(s["ids"]) if s else 0}
        log("indexed document", doc_id=doc_id, chunks=len(chunks), embedded=len(todo),
            reused=len(chunks) - len(todo), superseded=e.superseded)

    changed = any(stats[k] for k in ("docs_added", "docs_replaced", "docs_metadata_updated",
                                     "docs_removed"))
    final = counts_by_doc(col)
    total = sum(final.values())
    stats["index_id"] = (_stamp(col, settings, dimension, total) if changed
                         else str((col.metadata or {}).get("index_id", "none")))
    stats["chunks_total"] = total
    stats["chunks_by_doc_id"] = final
    stats["orphan_chunks"] = sum(n for d, n in final.items() if d not in desired)
    stats["missing_docs"] = sorted(d for d in desired if d not in final)
    return stats


def summary_line(stats: dict[str, Any]) -> str:
    keys = ("docs_added", "docs_replaced", "docs_metadata_updated", "docs_removed",
            "docs_unchanged", "chunks_embedded", "chunks_reused", "chunks_deleted",
            "orphan_chunks")
    return json.dumps({k: stats[k] for k in keys})
