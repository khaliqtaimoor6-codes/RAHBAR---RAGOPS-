"""The ingestion Job (Part A): ingest -> verify -> update the data lake -> update the
retrieval sources. It is the only writer to the vector store (Part F2).

    python -m pipeline.ingest                    # control files, verify new files, reconcile
    python -m pipeline.ingest --reconcile-only   # skip verification: rebuild/refresh a
                                                 # collection from the lake (Part C candidate)
    python -m pipeline.ingest --counts           # print chunks per doc_id and exit (read-only)

Operator actions, by dropping a control file into <lake>/inbox/ before a run:
    _delete.txt    one doc_id per line: remove the document and every chunk of it
    _restore.txt   one doc_id per line: make an archived version current again (rollback);
                   the version that replaced it is archived in turn

Exit code 0 = the run finished (documents may still have been quarantined: that is the
verification stage working). Non-zero = the run itself failed, and the Job retries.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from .config import IndexerSettings, get_settings
from .lake import Candidate, DocEntry, Lake, sha256_text
from .models import Document
from .verify import (
    CheckResult,
    Seen,
    Thresholds,
    Verdict,
    check_completeness,
    check_quality,
    check_recency,
    check_uniqueness,
    decide,
    injection_matches,
    status,
)

FINGERPRINT_WORDS = 1000


def peak_rss_mb() -> float | None:
    """Peak resident memory of this process in MiB (Linux: ru_maxrss is in KiB). A Job
    that finishes in seconds is gone before metrics-server samples it; this is not."""
    try:
        import resource

        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:
        return None


def log(msg: str, **fields: object) -> None:
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "logger": "rahbar.ingest", "msg": msg, **fields}), flush=True)


def fingerprint(doc: Document, settings: IndexerSettings) -> list[float]:
    """One vector for the whole document (its first ~1000 words), for near-duplicates."""
    from .embed import embed

    words = " ".join(p.text for p in doc.pages).split()
    return embed([" ".join(words[:FINGERPRINT_WORDS])], settings)[0]


# ----------------------------------------------------------------------- control files

def apply_controls(lake: Lake, run_id: str) -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = []
    for doc_id in lake.control_lines("_delete.txt"):
        e = lake.docs.get(doc_id)
        if e is None:
            ops.append({"op": "delete", "doc_id": doc_id, "result": "unknown doc_id"})
            continue
        lake.delete(e, run_id)
        ops.append({"op": "delete", "doc_id": doc_id, "result": "deleted (file kept in "
                    f"deleted/{run_id}/, chunks removed in reconcile)"})
    for doc_id in lake.control_lines("_restore.txt"):
        e = lake.docs.get(doc_id)
        if e is None or e.status != "archived":
            ops.append({"op": "restore", "doc_id": doc_id,
                        "result": "not an archived doc_id: nothing to restore"})
            continue
        demoted = []
        for other in lake.family_members(e.family):
            if other.doc_id != doc_id and other.status == "current":
                other.file = lake.archive_file(other)
                other.status = "archived"
                demoted.append(other.doc_id)
        e.file = lake.restore_file(e)
        e.status = "current"
        ops.append({"op": "restore", "doc_id": doc_id, "result": "current again",
                    "archived": demoted})
    lake.consume_control("_delete.txt", run_id)
    lake.consume_control("_restore.txt", run_id)
    for op in ops:
        log("control", **op)
    return ops


# ---------------------------------------------------------------------------- verify

def verify_one(cand: Candidate, cands: list[Candidate], lake: Lake, seen: list[Seen],
               settings: IndexerSettings, t: Thresholds) -> tuple[Verdict, Document | None,
                                                                  str, list[float]]:
    from .clean import clean
    from .extract import extract

    doc: Document | None = None
    error: str | None = None
    try:
        doc = clean(extract(str(cand.path), cand.meta.get("doc_version", "unknown"), False))
    except Exception as exc:                          # corrupt, truncated, unsupported
        error = f"{type(exc).__name__}: {str(exc)[:160]}"

    quality = check_quality(doc, error, t)
    completeness = check_completeness(cand, doc)
    peers = [c for c in cands if c is not cand]
    recency, supersedes = check_recency(cand, lake.family_members(cand.family), peers)
    text = "\n".join(p.text for p in doc.pages) if doc else ""
    text_sha = sha256_text(text) if text.split() else ""
    fp: list[float] = []
    if quality.passed:
        try:
            fp = fingerprint(doc, settings) if doc else []
        except Exception as exc:
            log("fingerprint failed; near-duplicate check limited to hashes",
                doc_id=cand.doc_id, error=str(exc)[:200])
    uniqueness = check_uniqueness(cand, text_sha, fp, seen, t)
    checks: list[CheckResult] = [quality, completeness, recency, uniqueness]
    verdict = Verdict(doc_id=cand.doc_id, file=cand.path.name, origin=cand.origin,
                      checks=checks, supersedes=supersedes)
    verdict.action = decide(checks)
    if doc is not None:
        verdict.injection_matches = injection_matches(doc)
        verdict.injection_suspect = bool(verdict.injection_matches)
    return verdict, doc, text_sha, fp


def verify_and_update_lake(lake: Lake, settings: IndexerSettings, run_id: str,
                           include_mirror: bool) -> list[Verdict]:
    t = Thresholds()
    cands = lake.candidates(include_mirror=include_mirror)
    seen = [Seen(e.doc_id, e.family, e.sha256, e.text_sha, e.fingerprint)
            for e in lake.docs.values()]
    rejected: dict[str, str] = lake.tombstones.get("__rejected__", {})  # sha -> run_id
    verdicts: list[Verdict] = []
    for cand in cands:
        existing = lake.docs.get(cand.doc_id)
        if existing and existing.sha256 == cand.sha256:
            if Path(existing.file).name == cand.path.name or cand.origin == "mirror":
                lake.drop_inbox_copy(cand)
                verdicts.append(Verdict(cand.doc_id, cand.path.name, cand.origin, [],
                                        action="unchanged"))
                continue
            # Same bytes under another file name: a copy (its front matter even carries
            # the same doc_id), not a re-delivery of the same file. Found in Batch B: b03
            # was a byte copy of b01 and the first version of this loop let it through as
            # "unchanged".
            dup = CheckResult("uniqueness", False,
                              f"exact duplicate of {existing.doc_id} (same file hash, "
                              f"different file name {cand.path.name})",
                              {"duplicate_of": existing.doc_id, "kind": "exact-bytes"})
            v = Verdict(cand.doc_id + "~" + cand.path.stem, cand.path.name, cand.origin,
                        [CheckResult("quality", None, "not run: byte-identical to an "
                                     "indexed document"),
                         CheckResult("completeness", None, "not run: byte-identical"),
                         CheckResult("recency", None, "not run: byte-identical"), dup],
                        action="quarantine")
            verdicts.append(v)
            log("verified", doc_id=v.doc_id, action=v.action, failed=v.failed)
            lake.quarantine(cand, run_id, v.as_dict())
            continue
        if cand.origin == "mirror" and (cand.doc_id in lake.tombstones
                                        or cand.sha256 in rejected):
            verdicts.append(Verdict(cand.doc_id, cand.path.name, cand.origin, [],
                                    action="skipped"))
            continue

        verdict, doc, text_sha, fp = verify_one(cand, cands, lake, seen, settings, t)
        verdicts.append(verdict)
        log("verified", doc_id=cand.doc_id, action=verdict.action, failed=verdict.failed,
            injection_suspect=verdict.injection_suspect)

        if verdict.action == "quarantine":
            lake.quarantine(cand, run_id, verdict.as_dict())
            if cand.origin == "mirror":
                rejected[cand.sha256] = run_id
            continue

        assert doc is not None
        if existing:                                   # a changed document: replace it
            old_path = lake.root / existing.file
            if old_path.exists():
                lake._move(old_path, lake.root / "deleted" / run_id, keep_source=False)
        if verdict.action == "archive":
            rel = lake.archive_candidate(cand)
            state = "archived"
        else:
            rel = lake.rel(lake.accept(cand))
            state = "current"
            for old_id in verdict.supersedes:
                old = lake.docs[old_id]
                old.file = lake.archive_file(old)
                old.status = "archived"
        entry = DocEntry(
            doc_id=cand.doc_id, family=cand.family, title=cand.meta.get("title", ""),
            source=cand.meta.get("source", ""), file=rel,
            doc_version=cand.meta.get("doc_version", "unknown"), sha256=cand.sha256,
            text_sha=text_sha, page_count=len(doc.pages), status=state,
            injection_suspect=verdict.injection_suspect, fingerprint=fp, run_id=run_id)
        lake.docs[cand.doc_id] = entry
        lake.save_extracted(cand.doc_id, doc)
        seen = [s for s in seen if s.doc_id != cand.doc_id]
        seen.append(Seen(entry.doc_id, entry.family, entry.sha256, entry.text_sha, fp))
    if rejected:
        lake.tombstones["__rejected__"] = rejected
    return verdicts


# ---------------------------------------------------------------------------- output

def print_verification_table(verdicts: list[Verdict], run_id: str) -> None:
    checked = [v for v in verdicts if v.checks]
    print(f"\n=== VERIFICATION REPORT  run={run_id}  checked={len(checked)}  "
          f"unchanged={sum(v.action == 'unchanged' for v in verdicts)}  "
          f"skipped={sum(v.action == 'skipped' for v in verdicts)} ===", flush=True)
    print(f"{'doc_id':44} {'quality':8} {'complete':9} {'recency':8} {'unique':7} "
          f"{'inject':7} action", flush=True)
    for v in checked:
        by = {c.name: c for c in v.checks}
        print(f"{v.doc_id[:44]:44} {status(by['quality']):8} {status(by['completeness']):9} "
              f"{status(by['recency']):8} {status(by['uniqueness']):7} "
              f"{'FLAG' if v.injection_suspect else '-':7} {v.action.upper()}", flush=True)
        for c in v.checks:
            if c.passed is not True:
                print(f"{'':6}- {c.name}: {c.reason}", flush=True)
        if v.injection_suspect:
            print(f"{'':6}- injection (advisory): {'; '.join(v.injection_matches[:3])}",
                  flush=True)
    print(flush=True)


def print_reconcile(stats: dict[str, Any]) -> None:
    print(f"=== INCREMENTAL UPDATE  collection={stats['collection']}  "
          f"index_id={stats['index_id']} ===", flush=True)
    for k in ("docs_added", "docs_replaced", "docs_metadata_updated", "docs_removed",
              "docs_unchanged", "chunks_embedded", "chunks_reused", "chunks_deleted",
              "chunks_metadata_updated", "chunks_total", "orphan_chunks"):
        print(f"  {k:26} {stats[k]}", flush=True)
    print("  chunks by doc_id (from Chroma):", flush=True)
    for d, n in stats["chunks_by_doc_id"].items():
        print(f"    {d or '(no doc_id)':52} {n}", flush=True)
    print(flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="RAHBAR ingestion with verification.")
    parser.add_argument("--reconcile-only", action="store_true",
                        help="skip verification; bring the collection in line with the lake")
    parser.add_argument("--no-mirror", action="store_true",
                        help="only look at the inbox, not the fetched public corpus")
    parser.add_argument("--counts", action="store_true",
                        help="print chunks per doc_id in the collection and exit")
    args = parser.parse_args()
    settings = get_settings()
    from .store import get_client

    if args.counts:
        from .reconcile import counts_by_doc, open_collection

        counts = counts_by_doc(open_collection(get_client(settings), settings))
        print(json.dumps({"collection": settings.collection, "chunks_by_doc_id": counts,
                          "total": sum(counts.values())}, indent=1))
        return 0

    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    lake = Lake(settings.lake_dir)
    lake.acquire_lock(run_id)
    started = time.perf_counter()
    log("ingestion starting", run_id=run_id, collection=settings.collection,
        embed_model=settings.embed_model, lake=settings.lake_dir,
        reconcile_only=args.reconcile_only, pod=os.environ.get("HOSTNAME", "-"))
    try:
        ops = apply_controls(lake, run_id)
        verdicts: list[Verdict] = []
        if not args.reconcile_only:
            verdicts = verify_and_update_lake(lake, settings, run_id,
                                              include_mirror=not args.no_mirror)
        lake.save()
        report = {"run_id": run_id, "collection": settings.collection,
                  "controls": ops, "documents": [v.as_dict() for v in verdicts],
                  "summary": {a: sum(v.action == a for v in verdicts) for a in
                              ("index", "archive", "quarantine", "unchanged", "skipped")}}
        if verdicts:
            path = lake.write_report("verify", run_id, report)
            print_verification_table(verdicts, run_id)
            log("verification report written", path=str(path), **report["summary"])

        from .embed import embed
        from .reconcile import reconcile, summary_line

        stats = reconcile(lake, settings, get_client(settings), embed, log=log)
        lake.save()
        stats["seconds"] = round(time.perf_counter() - started, 1)
        stats["peak_rss_mb"] = peak_rss_mb()       # F5: the Job measures itself
        lake.write_report("ingest", run_id, {**stats, "controls": ops,
                                             "verification": report["summary"]})
        print_reconcile(stats)
        log("ingestion finished", run_id=run_id, seconds=stats["seconds"],
            peak_rss_mb=stats["peak_rss_mb"],
            summary=json.loads(summary_line(stats)))
        if stats["orphan_chunks"]:
            log("orphan chunks left in the collection", count=stats["orphan_chunks"])
            return 3
        return 0
    finally:
        lake.release_lock()


if __name__ == "__main__":
    sys.exit(main())
