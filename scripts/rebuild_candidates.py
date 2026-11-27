#!/usr/bin/env python
"""Rebuild a candidate collection from the live `rahbar` collection.

The restored k3d cluster no longer has the data-lake PVC, so a full OCR re-ingest is not
possible without re-downloading and re-OCRing the corpus (hours on this CPU-only box).
This script reconstructs per-page text from the chunks already indexed in `rahbar`, then
runs the pipeline's own chunker and embedder to build a candidate collection. Only the
text source differs; CHUNK_SIZE/CHUNK_OVERLAP and the embedding model are the pipeline's.

Usage (inside the indexer image):
    python /tmp/rebuild.py --target rahbar-cand-cs300 --size 300 --overlap 50
    python /tmp/rebuild.py --target rahbar-cand-cs100 --size 100 --overlap 20
    python /tmp/rebuild.py --dry-run --limit 2 --target x --size 300 --overlap 50
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import re
import sys
import time

sys.path.insert(0, "/app")

from pipeline.chunk import chunk  # noqa: E402
from pipeline.config import get_settings  # noqa: E402
from pipeline.embed import embed  # noqa: E402
from pipeline.models import Document, Page  # noqa: E402
from pipeline.store import get_client, store  # noqa: E402


def strip_header(text: str, section: str) -> str:
    first, sep, rest = text.partition("\n")
    if sep and first.strip() == section.strip():
        return rest
    return text


def merge_overlap(prev: str, nxt: str, max_words: int = 40) -> str:
    """Join two chunk bodies, removing the chunker's word overlap."""
    if not prev:
        return nxt
    pw, nw = prev.split(), nxt.split()
    for k in range(min(max_words, len(pw), len(nw)), 0, -1):
        if pw[-k:] == nw[:k]:
            return " ".join(pw + nw[k:])
    return prev + " " + nxt


def reconstruct(client, source_collection: str) -> list[Document]:
    col = client.get_collection(source_collection)
    res = col.get(include=["documents", "metadatas"])
    by_source: dict[str, list[tuple[int, str, str, dict]]] = collections.defaultdict(list)
    for id_, text, md in zip(res["ids"], res["documents"], res["metadatas"]):
        m = re.search(r"-(\d{4})$", id_)
        by_source[md.get("source", "unknown")].append(
            (int(m.group(1)) if m else 0, id_, text or "", md)
        )
    docs: list[Document] = []
    for source, items in sorted(by_source.items()):
        items.sort(key=lambda x: x[0])
        first = items[0][3]
        pages: list[Page] = []
        cur_page: int | None = None
        cur_text = ""
        for _, _, text, md in items:
            page = int(md.get("page", 1))
            section = md.get("section", "")
            body = strip_header(text, section)
            if cur_page is None:
                cur_page = page
            if page != cur_page:
                pages.append(Page(source=source, page=cur_page, text=cur_text))
                cur_page, cur_text = page, ""
            cur_text = merge_overlap(cur_text, body)
        if cur_page is not None:
            pages.append(Page(source=source, page=cur_page, text=cur_text))
        docs.append(
            Document(
                source=source,
                doc_version=first.get("doc_version", "unknown"),
                superseded=bool(first.get("superseded", False)),
                pages=pages,
            )
        )
    return docs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="rahbar")
    ap.add_argument("--target", required=True)
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--overlap", type=int, required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    settings = dataclasses.replace(
        get_settings(),
        collection=args.target,
        chunk_size=args.size,
        chunk_overlap=args.overlap,
    )
    client = get_client(settings)
    docs = reconstruct(client, args.source)
    if args.limit:
        docs = docs[: args.limit]
    chunks = []
    for doc in docs:
        chunks.extend(chunk(doc, args.size, args.overlap))
    counts = collections.Counter(c.source for c in chunks)
    print(
        json.dumps(
            {
                "msg": "reconstructed",
                "docs": len(docs),
                "chunks": len(chunks),
                "target": args.target,
                "by_source": dict(sorted(counts.items())),
            }
        ),
        flush=True,
    )
    if args.dry_run:
        return 0
    started = time.time()
    vectors = embed([c.text for c in chunks], settings)
    print(
        json.dumps(
            {
                "msg": "embedded",
                "chunks": len(vectors),
                "seconds": round(time.time() - started, 1),
            }
        ),
        flush=True,
    )
    n = store(chunks, vectors, settings, client)
    print(
        json.dumps(
            {
                "msg": "stored",
                "collection": args.target,
                "chunks": n,
                "by_source": dict(sorted(counts.items())),
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
