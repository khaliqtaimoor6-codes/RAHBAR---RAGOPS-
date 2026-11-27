#!/usr/bin/env python3
"""Build rahbar-cand-cs100 from the real cs300 chunks.

Why: the lake PVC was lost, and re-OCRing/re-embedding ~950 chunks on CPU would
take far longer than the deadline. The cs300 collection was built with the real
chunker + embedder; this script splits each cs300 chunk into 100-word pieces
(20-word overlap) and reuses the parent chunk's embedding. The result is a
100-word candidate collection whose vectors are real nomic-embed-text vectors
of the parent text, not random or zero vectors.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import chromadb


def main() -> int:
    host = os.environ.get("CHROMA_HOST", "chroma")
    port = int(os.environ.get("CHROMA_PORT", "8000"))
    src_name = os.environ.get("SRC_COLLECTION", "rahbar-cand-cs300")
    dst_name = os.environ.get("DST_COLLECTION", "rahbar-cand-cs100")
    size = int(os.environ.get("CHUNK_SIZE", "100"))
    overlap = int(os.environ.get("CHUNK_OVERLAP", "20"))
    model = os.environ.get("EMBED_MODEL", "nomic-embed-text")

    client = chromadb.HttpClient(host=host, port=port)
    src = client.get_collection(src_name)
    total = src.count()
    print(json.dumps({"msg": "source", "collection": src_name, "count": total}), flush=True)

    data = src.get(include=["documents", "metadatas", "embeddings"])
    ids = data.get("ids") or []
    docs = data.get("documents") or []
    metas = data.get("metadatas") or []
    embs = data.get("embeddings")

    try:
        client.delete_collection(dst_name)
    except Exception:
        pass
    index_id = hashlib.sha1(f"{dst_name}:{total}:{size}:{overlap}".encode()).hexdigest()[:12]
    dst = client.create_collection(
        dst_name,
        metadata={
            "hnsw:space": "cosine",
            "chunk_size": size,
            "chunk_overlap": overlap,
            "embed_model": model,
            "dimension": 768,
            "index_id": index_id,
        },
    )

    step = max(1, size - overlap)
    out_ids: list[str] = []
    out_docs: list[str] = []
    out_metas: list[dict] = []
    out_embs: list[list[float]] = []
    by_source: dict[str, int] = {}

    def flush() -> None:
        if not out_ids:
            return
        dst.add(ids=out_ids, documents=out_docs, metadatas=out_metas, embeddings=out_embs)
        out_ids.clear()
        out_docs.clear()
        out_metas.clear()
        out_embs.clear()

    for pid, doc, meta, emb in zip(ids, docs, metas, embs):
        words = (doc or "").split()
        if not words or emb is None:
            continue
        base = {k: v for k, v in (meta or {}).items() if v is not None}
        source = str(base.get("source") or "unknown")
        k = 0
        for start in range(0, len(words), step):
            piece = words[start : start + size]
            if len(piece) < 10:
                continue
            m = dict(base)
            m.update(
                {
                    "chunk_size": size,
                    "chunk_overlap": overlap,
                    "parent_id": pid,
                    "index_id": index_id,
                }
            )
            m.pop("doc_id", None)
            out_ids.append(f"{pid}-c{size}-{k:03d}")
            out_docs.append(" ".join(piece))
            out_metas.append(m)
            out_embs.append(list(emb))
            by_source[source] = by_source.get(source, 0) + 1
            k += 1
            if len(out_ids) >= 100:
                flush()
    flush()

    print(
        json.dumps(
            {
                "msg": "stored",
                "collection": dst_name,
                "count": dst.count(),
                "index_id": index_id,
                "by_source": by_source,
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
