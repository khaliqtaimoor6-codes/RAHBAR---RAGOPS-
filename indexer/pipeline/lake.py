"""The data lake (RAGOps paper 4.2.3): where documents live before, during and after
indexing. It sits on a PersistentVolumeClaim, so it survives pod restarts.

    <LAKE_DIR>/
      mirror/        the public corpus, fetched by the Job's init container (kept)
      inbox/         new batches dropped by an operator (consumed by each run)
                     + control files: _delete.txt, _restore.txt (one doc_id per line)
      current/       accepted documents: the retrieval sources
      archive/<family>/<doc_version>/   superseded versions (still indexed, superseded=true)
      quarantine/<run_id>/              documents that failed verification + a reason file
      deleted/<run_id>/                 documents removed by an operator (audit trail)
      extracted/<doc_id>.json           cleaned text, so re-chunking never re-runs OCR
      reports/       verify-<run_id>.json, ingest-<run_id>.json
      state/registry.json               the lake's view: one entry per document

The registry is the desired state; each Chroma collection is a derived view of it that
pipeline/reconcile.py brings in line. A candidate collection (Part C) is therefore just
another reconcile of the same lake with different chunking or embedding settings.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import Document, Page

SUPPORTED = {".pdf", ".md", ".txt", ".html", ".htm"}
CONTROL_FILES = {"_delete.txt", "_restore.txt"}


def slug(text: str, limit: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit] or "doc"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Hash of the text with all whitespace collapsed: the same words give the same hash
    whatever the line wrapping, so a re-saved copy is still an exact duplicate."""
    return hashlib.sha256(" ".join(text.split()).lower().encode("utf-8")).hexdigest()


def version_key(version: str) -> tuple[int, ...]:
    """'2026-06' -> (2026, 6); '2019-20' -> (2019, 20); 'v3' -> (3,). Unknown -> ()."""
    return tuple(int(n) for n in re.findall(r"\d+", version or ""))


def front_matter(text: str) -> dict[str, str]:
    """`key: value` lines between leading '---' markers."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        if key.strip():
            meta[key.strip()] = value.strip().strip('"')
    return meta


def pdf_info(path: Path) -> dict[str, str]:
    """The PDF's document-info dictionary (Title, CreationDate, ModDate ...), or {}."""
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            return {k: str(v) for k, v in (pdf.metadata or {}).items()}
    except Exception:
        return {}


@dataclass
class Candidate:
    """A file offered to the verification stage in this run."""

    path: Path
    origin: str                      # "mirror" (public corpus) or "inbox" (a new batch)
    sha256: str
    meta: dict[str, str] = field(default_factory=dict)

    @property
    def doc_id(self) -> str:
        return self.meta.get("doc_id") or slug(self.path.stem)

    @property
    def family(self) -> str:
        return self.meta.get("family") or self.doc_id


@dataclass
class DocEntry:
    """One document in the registry."""

    doc_id: str
    family: str
    title: str
    source: str                      # where it came from (URL or 'inbox:<batch>')
    file: str                        # path relative to the lake root
    doc_version: str
    sha256: str                      # raw bytes
    text_sha: str                    # normalised text
    page_count: int
    status: str                      # "current" or "archived"
    injection_suspect: bool = False
    fingerprint: list[float] = field(default_factory=list)
    run_id: str = ""

    @property
    def superseded(self) -> bool:
        return self.status == "archived"


class Lake:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        for sub in ("mirror", "inbox", "current", "archive", "quarantine", "deleted",
                    "extracted", "reports", "state"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        self.registry_path = self.root / "state" / "registry.json"
        self.docs: dict[str, DocEntry] = {}
        self.tombstones: dict[str, dict[str, Any]] = {}
        self.load()

    # ------------------------------------------------------------------ registry
    def load(self) -> None:
        if not self.registry_path.exists():
            return
        raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.docs = {d: DocEntry(**e) for d, e in raw.get("docs", {}).items()}
        self.tombstones = raw.get("tombstones", {})

    def save(self) -> None:
        tmp = self.registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"docs": {d: asdict(e) for d, e in self.docs.items()},
                                   "tombstones": self.tombstones}, indent=1),
                       encoding="utf-8")
        os.replace(tmp, self.registry_path)          # atomic: never a half-written registry

    def family_members(self, family: str) -> list[DocEntry]:
        return [e for e in self.docs.values() if e.family == family]

    # ------------------------------------------------------------------ lock
    def acquire_lock(self, run_id: str, stale_after: int = 3 * 3600) -> None:
        """One writer at a time, on top of the CronJob's concurrencyPolicy: Forbid
        (a manual `kubectl create job` can still overlap a scheduled one)."""
        lock = self.root / "state" / ".lock"
        if lock.exists():
            held = json.loads(lock.read_text(encoding="utf-8") or "{}")
            if time.time() - float(held.get("since", 0)) < stale_after:
                raise SystemExit(f"lake is locked by run {held.get('run_id')}; refusing to "
                                 "run two writers at once")
        lock.write_text(json.dumps({"run_id": run_id, "since": time.time()}), encoding="utf-8")

    def release_lock(self) -> None:
        (self.root / "state" / ".lock").unlink(missing_ok=True)

    # ------------------------------------------------------------------ discovery
    def candidates(self, include_mirror: bool = True) -> list[Candidate]:
        """Every file offered in this run: the mirror first (the base corpus), then the
        inbox in name order, so within-batch duplicates are judged deterministically."""
        found: list[Candidate] = []
        if include_mirror:
            found.extend(self._mirror_candidates())
        inbox = self.root / "inbox"
        for path in sorted(p for p in inbox.rglob("*") if p.is_file()):
            if path.name in CONTROL_FILES or path.name.endswith(".meta.json"):
                continue
            if path.suffix.lower() not in SUPPORTED and path.suffix.lower() != ".bin":
                continue
            data = path.read_bytes()
            found.append(Candidate(path=path, origin="inbox", sha256=sha256_bytes(data),
                                   meta=self._inbox_meta(path, data)))
        return found

    def _mirror_candidates(self) -> list[Candidate]:
        index = self.root / "mirror" / "_index.json"
        if not index.exists():
            return []
        out = []
        for e in json.loads(index.read_text(encoding="utf-8")):
            path = self.root / "mirror" / e["file"]
            if not path.exists():
                continue
            doc_id = slug(Path(e["file"]).stem)
            meta = {"doc_id": doc_id, "family": e.get("family") or doc_id,
                    "title": e.get("name", ""), "source": e.get("url", ""),
                    "doc_version": str(e.get("doc_version", ""))}
            out.append(Candidate(path=path, origin="mirror",
                                 sha256=sha256_bytes(path.read_bytes()), meta=meta))
        return out

    def _inbox_meta(self, path: Path, data: bytes) -> dict[str, str]:
        """Metadata for a dropped file, in this order:
        1. a sidecar '<file>.meta.json' (any format);
        2. Markdown/text: front matter only (a text file can always declare it, so a
           missing key there is a real completeness failure);
        3. PDF/HTML without a sidecar: derived from the file itself (PDF info dates and
           Title, HTML <title>), source = its inbox path. Derived keys are listed under
           `_derived` and shown in the verification report. Anything that cannot be
           derived stays missing, and the completeness check notices."""
        sidecar = path.with_name(path.name + ".meta.json")
        if sidecar.exists():
            raw = json.loads(sidecar.read_text(encoding="utf-8"))
            return {k: str(v) for k, v in raw.items() if v not in (None, "")}
        suffix = path.suffix.lower()
        if suffix in {".md", ".txt"}:
            return front_matter(data.decode("utf-8", "replace"))
        meta: dict[str, str] = {"source": "inbox:" + path.relative_to(self.root / "inbox").as_posix()}
        derived = ["source"]
        if suffix == ".pdf":
            info = pdf_info(path)
            date = re.match(r"D:(\d{4})(\d{2})", info.get("ModDate") or info.get("CreationDate") or "")
            if date:
                meta["doc_version"] = f"{date.group(1)}-{date.group(2)}"
                derived.append("doc_version")
            title = (info.get("Title") or "").strip()
            if title and not title.lower().startswith(("microsoft word", "untitled")):
                meta["title"] = title
                derived.append("title")
        elif suffix in {".html", ".htm"}:
            m = re.search(r"<title[^>]*>(.*?)</title>", data.decode("utf-8", "replace"), re.I | re.S)
            if m and m.group(1).strip():
                meta["title"] = " ".join(m.group(1).split())
                derived.append("title")
        meta["_derived"] = ",".join(derived)
        return meta

    def control_lines(self, name: str) -> list[str]:
        path = self.root / "inbox" / name
        if not path.exists():
            return []
        return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")]

    def consume_control(self, name: str, run_id: str) -> None:
        path = self.root / "inbox" / name
        if path.exists():
            dest = self.root / "reports" / f"{run_id}{name}"
            shutil.move(str(path), dest)

    # ------------------------------------------------------------------ file moves
    def _move(self, src: Path, dest_dir: Path, keep_source: bool) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        if keep_source:
            shutil.copy2(src, dest)
        else:
            shutil.move(str(src), dest)
            sidecar = src.with_name(src.name + ".meta.json")
            if sidecar.exists():
                shutil.move(str(sidecar), dest_dir / sidecar.name)
        return dest

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def accept(self, cand: Candidate) -> Path:
        """Copy (mirror) or move (inbox) into current/."""
        return self._move(cand.path, self.root / "current", keep_source=cand.origin == "mirror")

    def archive_file(self, entry: DocEntry) -> str:
        """Move a document's file to archive/<family>/<version>/ and return its new path."""
        src = self.root / entry.file
        dest_dir = self.root / "archive" / entry.family / slug(entry.doc_version or "unknown")
        if not src.exists():
            return entry.file
        if src.parent == dest_dir:
            return entry.file
        return self.rel(self._move(src, dest_dir, keep_source=False))

    def archive_candidate(self, cand: Candidate) -> str:
        dest_dir = self.root / "archive" / cand.family / slug(cand.meta.get("doc_version") or "unknown")
        return self.rel(self._move(cand.path, dest_dir, keep_source=cand.origin == "mirror"))

    def restore_file(self, entry: DocEntry) -> str:
        src = self.root / entry.file
        if not src.exists() or src.parent == self.root / "current":
            return entry.file
        return self.rel(self._move(src, self.root / "current", keep_source=False))

    def quarantine(self, cand: Candidate, run_id: str, reasons: dict[str, Any]) -> str:
        dest_dir = self.root / "quarantine" / run_id
        dest = self._move(cand.path, dest_dir, keep_source=cand.origin == "mirror")
        (dest_dir / (cand.path.name + ".reason.json")).write_text(
            json.dumps(reasons, indent=1), encoding="utf-8")
        return self.rel(dest)

    def delete(self, entry: DocEntry, run_id: str) -> None:
        src = self.root / entry.file
        if src.exists():
            self._move(src, self.root / "deleted" / run_id, keep_source=False)
        self.tombstones[entry.doc_id] = {"run_id": run_id, "sha256": entry.sha256,
                                         "family": entry.family}
        (self.root / "extracted" / f"{entry.doc_id}.json").unlink(missing_ok=True)
        del self.docs[entry.doc_id]

    def drop_inbox_copy(self, cand: Candidate) -> None:
        """An inbox file that is byte-identical to what we already hold: nothing to do."""
        if cand.origin == "inbox":
            cand.path.unlink(missing_ok=True)
            cand.path.with_name(cand.path.name + ".meta.json").unlink(missing_ok=True)

    # ------------------------------------------------------------------ extracted text
    def save_extracted(self, doc_id: str, doc: Document) -> None:
        (self.root / "extracted" / f"{doc_id}.json").write_text(
            json.dumps(asdict(doc)), encoding="utf-8")

    def load_extracted(self, doc_id: str) -> Document | None:
        path = self.root / "extracted" / f"{doc_id}.json"
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
        return Document(source=d["source"], doc_version=d["doc_version"],
                        superseded=d["superseded"], pages=[Page(**p) for p in d["pages"]])

    def write_report(self, kind: str, run_id: str, payload: dict[str, Any]) -> Path:
        path = self.root / "reports" / f"{kind}-{run_id}.json"
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        return path
