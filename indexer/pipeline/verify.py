"""A1: the verification stage (RAGOps paper 4.2.2). Runs after extraction and before
chunking. Every document gets pass/fail with a reason for four checks:

  quality       empty, garbled, or failed extraction
  completeness  required metadata (source, title, doc_version, page count); not truncated
  recency       is a newer version of the same document (same family) known?
  uniqueness    exact duplicate (byte or text hash) or near-duplicate (embedding cosine)

A fifth, advisory signal is recorded but never fails a document: `injection_suspect`,
text that reads like instructions to a model. The document is still indexed (it is a real
policy document that happens to contain the text, or a planted test); the API's retrieval
rail decides what to do with such chunks at query time and logs it in the trace (D4).

Decision: a failed quality, completeness or uniqueness check -> quarantine (not indexed).
A failed recency check alone -> archive (indexed with superseded=true, so retrieval
excludes it unless a user asks for the older edition, and it can be restored).
Every threshold is an environment variable from the ConfigMap, so it can be tuned without
rebuilding the image.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Any

from .lake import Candidate, DocEntry, version_key
from .models import Document

REQUIRED_META = ("source", "title", "doc_version")


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


@dataclass
class Thresholds:
    min_words: int = int(os.environ.get("VERIFY_MIN_WORDS", 40))
    # Share of non-space characters that are letters, digits or ordinary punctuation.
    # Real corpus documents measure >= 0.93; mojibake / binary noise falls far below.
    min_clean_char_ratio: float = _env_float("VERIFY_MIN_CLEAN_CHARS", 0.85)
    # Share of word-like tokens that look like words (letters, optionally with digits).
    min_wordlike_ratio: float = _env_float("VERIFY_MIN_WORDLIKE", 0.55)
    near_dup_cosine: float = _env_float("NEAR_DUP_THRESHOLD", 0.985)


@dataclass
class CheckResult:
    name: str
    passed: bool | None              # None = not run (e.g. nothing was extracted)
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Verdict:
    doc_id: str
    file: str
    origin: str
    checks: list[CheckResult]
    action: str = ""                 # index | archive | quarantine | unchanged | skipped
    injection_suspect: bool = False
    injection_matches: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)

    @property
    def failed(self) -> list[str]:
        return [c.name for c in self.checks if c.passed is False]

    def as_dict(self) -> dict[str, Any]:
        return {"doc_id": self.doc_id, "file": self.file, "origin": self.origin,
                "action": self.action, "failed": self.failed,
                "injection_suspect": self.injection_suspect,
                "injection_matches": self.injection_matches, "supersedes": self.supersedes,
                "checks": {c.name: {"result": status(c), "reason": c.reason, **c.details}
                           for c in self.checks}}


# ---------------------------------------------------------------------------- quality

_WORD = re.compile(r"\S+")
_WORDLIKE = re.compile(r"^[(\['\"]?[A-Za-z][A-Za-z'\-]*[A-Za-z0-9]?[.,;:!?)\]'\"%]*$")
_CLEAN_CHARS = re.compile(r"[A-Za-z0-9.,;:!?()\[\]'\"%/&\-|#*+=<>@$_–—•‘’“”…]")


def text_stats(doc: Document) -> dict[str, float]:
    text = "\n".join(p.text for p in doc.pages)
    words = _WORD.findall(text)
    nonspace = [ch for ch in text if not ch.isspace()]
    clean = sum(1 for ch in nonspace if _CLEAN_CHARS.match(ch))
    alpha_tokens = [w for w in words if any(c.isalpha() for c in w)]
    wordlike = sum(1 for w in alpha_tokens if _WORDLIKE.match(w))
    return {
        "words": len(words),
        "chars": len(nonspace),
        "clean_char_ratio": round(clean / len(nonspace), 4) if nonspace else 0.0,
        "wordlike_ratio": round(wordlike / len(alpha_tokens), 4) if alpha_tokens else 0.0,
        "replacement_chars": text.count("�"),
        "empty_pages": sum(1 for p in doc.pages if len(p.text.strip()) < 25),
        "pages": len(doc.pages),
    }


def check_quality(doc: Document | None, extract_error: str | None, t: Thresholds
                  ) -> CheckResult:
    if extract_error is not None or doc is None:
        return CheckResult("quality", False, f"extraction failed: {extract_error}")
    s = text_stats(doc)
    if s["words"] < t.min_words:
        return CheckResult("quality", False,
                           f"empty: {s['words']} words extracted (< {t.min_words})", s)
    if s["clean_char_ratio"] < t.min_clean_char_ratio or s["replacement_chars"] > 0.01 * s["chars"]:
        return CheckResult("quality", False,
                           f"garbled: clean-character ratio {s['clean_char_ratio']} "
                           f"(< {t.min_clean_char_ratio}), {s['replacement_chars']} U+FFFD", s)
    if s["wordlike_ratio"] < t.min_wordlike_ratio:
        return CheckResult("quality", False,
                           f"garbled: only {s['wordlike_ratio']:.0%} of tokens look like words "
                           f"(< {t.min_wordlike_ratio:.0%})", s)
    return CheckResult("quality", True,
                       f"{s['words']} words over {s['pages']} page(s); clean-character "
                       f"ratio {s['clean_char_ratio']}", s)


# ---------------------------------------------------------------------- completeness

_SENTENCE_END = re.compile(r"[.!?:;)\]\"'”|*_`>]\s*$")


def looks_truncated(cand: Candidate, doc: Document) -> str | None:
    """A reason string when the document looks cut short, else None."""
    suffix = cand.path.suffix.lower()
    if suffix == ".pdf":
        tail = cand.path.read_bytes()[-2048:]
        if b"%%EOF" not in tail:
            return "PDF has no %%EOF trailer (file cut short)"
    declared = cand.meta.get("page_count")
    if declared and declared.isdigit() and int(declared) != len(doc.pages):
        return f"metadata says {declared} pages, extracted {len(doc.pages)}"
    if suffix in {".md", ".txt"}:
        lines = [ln.strip() for ln in doc.pages[-1].text.splitlines() if ln.strip()]
        last = lines[-1] if lines else ""
        # Prose that stops mid-sentence: a long last line with no closing punctuation.
        if len(last.split()) >= 8 and not _SENTENCE_END.search(last):
            return f"text ends mid-sentence: '...{last[-60:]}'"
    return None


def check_completeness(cand: Candidate, doc: Document | None) -> CheckResult:
    missing = [k for k in REQUIRED_META if not cand.meta.get(k)]
    pages = len(doc.pages) if doc else 0
    details: dict[str, Any] = {"missing": missing, "page_count": pages,
                               "metadata": {k: cand.meta.get(k, "") for k in REQUIRED_META},
                               "derived": cand.meta.get("_derived", "")}
    if doc is None:
        return CheckResult("completeness", None, "not run: nothing was extracted", details)
    if pages == 0:
        missing.append("page_count")
    if missing:
        return CheckResult("completeness", False,
                           f"missing required metadata: {', '.join(missing)}", details)
    cut = looks_truncated(cand, doc)
    if cut:
        return CheckResult("completeness", False, f"truncated: {cut}", details)
    derived = f" (derived from the file: {cand.meta['_derived']})" if cand.meta.get("_derived") else ""
    return CheckResult("completeness", True,
                       f"source, title, doc_version={cand.meta['doc_version']}, "
                       f"{pages} page(s); not truncated{derived}", details)


# --------------------------------------------------------------------------- recency

def check_recency(cand: Candidate, known: list[DocEntry], peers: list[Candidate]
                  ) -> tuple[CheckResult, list[str]]:
    """Fail when a newer version of the same family is already in the lake or arrives in
    the same run. Returns (result, doc_ids this candidate supersedes)."""
    mine = version_key(cand.meta.get("doc_version", ""))
    newer: list[str] = []
    older: list[str] = []
    for e in known:
        if e.doc_id == cand.doc_id:
            continue
        theirs = version_key(e.doc_version)
        if theirs > mine:
            newer.append(f"{e.doc_id} ({e.doc_version})")
        elif theirs < mine and e.status == "current":
            older.append(e.doc_id)
    for p in peers:
        if p.doc_id != cand.doc_id and p.family == cand.family:
            if version_key(p.meta.get("doc_version", "")) > mine:
                newer.append(f"{p.doc_id} ({p.meta.get('doc_version')}, same batch)")
    details = {"family": cand.family, "doc_version": cand.meta.get("doc_version", "")}
    if newer:
        return CheckResult("recency", False, "superseded: newer version " + ", ".join(newer),
                           details), []
    reason = (f"latest version of '{cand.family}'"
              + (f"; supersedes {', '.join(older)}" if older else ""))
    return CheckResult("recency", True, reason, details), older


# ------------------------------------------------------------------------ uniqueness

def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class Seen:
    """Something an incoming document can duplicate: a registry entry or an earlier
    candidate accepted in this run."""

    doc_id: str
    family: str
    sha256: str
    text_sha: str
    fingerprint: list[float]


def check_uniqueness(cand: Candidate, text_sha: str, fingerprint: list[float],
                     seen: list[Seen], t: Thresholds) -> CheckResult:
    best_id, best = "", 0.0
    for s in seen:
        if s.doc_id == cand.doc_id:
            continue                      # an update of the same document, not a copy
        if s.sha256 == cand.sha256:
            return CheckResult("uniqueness", False,
                               f"exact duplicate of {s.doc_id} (same file hash)",
                               {"duplicate_of": s.doc_id, "kind": "exact-bytes"})
        if s.text_sha == text_sha:
            return CheckResult("uniqueness", False,
                               f"exact duplicate of {s.doc_id} (same text)",
                               {"duplicate_of": s.doc_id, "kind": "exact-text"})
        if s.family == cand.family:
            continue                      # versions of one document are meant to be similar
        if fingerprint and s.fingerprint:
            sim = cosine(fingerprint, s.fingerprint)
            if sim > best:
                best_id, best = s.doc_id, sim
    details = {"nearest": best_id, "cosine": round(best, 4),
               "threshold": t.near_dup_cosine}
    if best >= t.near_dup_cosine:
        return CheckResult("uniqueness", False,
                           f"near-duplicate of {best_id} (cosine {best:.4f} >= "
                           f"{t.near_dup_cosine})", details)
    return CheckResult("uniqueness", True,
                       f"unique; nearest {best_id or '-'} at cosine {best:.4f}", details)


# ------------------------------------------------------------------ injection (advisory)

INJECTION_PATTERNS = [
    r"ignore (?:all |any )?(?:the )?(?:previous|prior|above|earlier|your) (?:instructions|rules)",
    r"disregard (?:all |any )?(?:the )?(?:previous|prior|above|your) (?:instructions|rules)",
    r"you are now (?:a|an|in)\b",
    r"(?:reveal|print|show) (?:your|the) (?:system )?prompt",
    r"system prompt",
    r"new instructions?:",
    r"(?:assistant|ai|model|chatbot)s? (?:must|should) (?:always )?(?:say|answer|respond|tell)",
]
_INJECTION = re.compile("|".join(f"(?:{p})" for p in INJECTION_PATTERNS), re.I)


def injection_matches(doc: Document) -> list[str]:
    hits = []
    for page in doc.pages:
        for m in _INJECTION.finditer(page.text):
            hits.append(f"p{page.page}: '{m.group(0)}'")
    return hits[:10]


def status(c: CheckResult) -> str:
    return "SKIP" if c.passed is None else ("PASS" if c.passed else "FAIL")


def decide(checks: list[CheckResult]) -> str:
    failed = {c.name for c in checks if c.passed is False}
    if failed & {"quality", "completeness", "uniqueness"}:
        return "quarantine"
    if "recency" in failed:
        return "archive"
    return "index"
