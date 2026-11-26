"""Builds eval/golden.jsonl (Assignment 03, Part B) from:

* eval/golden.yaml — the 21 questions the group wrote by hand for Assignment 02, from the
  documents themselves, before any tuning (labelled `human`);
* SYNTHETIC below — 13 questions drafted with AI assistance for Assignment 03 (labelled
  `synthetic`). Each has `reviewed: false` until a group member has checked the question,
  the expected answer and the ground-truth clause against the document, and set it to the
  reviewer's name (eval/REVIEW-SYNTHETIC.md lists what to check);
* eval/index_sections.json — (source, section, page, doc_id) of every chunk in the live
  index (exported from Chroma, no text), used to fill in the ground-truth page numbers.

    python eval/build_golden.py

Ground truth per answerable question: the document (doc_id + file) and the clause/section,
plus the page(s) on which the index holds that clause. A question whose clause cannot be
found in the index is reported, never given an invented page.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_eval import section_matches  # noqa: E402  (Assignment 02's clause matcher)

SYNTHETIC = [
    # ---------------------------------------------------------------- unanswerable (4)
    {"id": "a03", "type": "abstain", "hard": False,
     "question": "Are students allowed to keep pets in their rooms on campus?",
     "relevant": [], "must_abstain": True},
    {"id": "a04", "type": "abstain", "hard": False,
     "question": "How much does a lunch meal cost in the university cafeteria?",
     "relevant": [], "must_abstain": True,
     "note": "the cafeteria page (demo batch c03) was quarantined, so nothing covers this"},
    {"id": "a05", "type": "abstain", "hard": False,
     "question": "Who won the 2022 FIFA World Cup?",
     "relevant": [], "must_abstain": True},
    {"id": "a06", "type": "abstain", "hard": False,
     "question": "What is the monthly parking fee for a student's car?",
     "relevant": [], "must_abstain": True},
    # ---------------------------------------------------------------- hard (9)
    {"id": "h01", "type": "paraphrase", "hard": True,
     "question": "If my overall GPA keeps sitting under two for three terms straight, what happens to my enrolment?",
     "relevant": [{"source": "academic-rules-handbook-jun-2026.pdf", "section": "5.6"}],
     "expect": "closed"},
    {"id": "h02", "type": "multi-chunk", "hard": True,
     "question": "What CGPA puts a student on academic warning, and what happens if it stays that low for three semesters?",
     "relevant": [{"source": "academic-rules-handbook-jun-2026.pdf", "section": "5.4"},
                  {"source": "academic-rules-handbook-jun-2026.pdf", "section": "5.6"}],
     "expect": "2.00"},
    {"id": "h03", "type": "paraphrase", "hard": True,
     "question": "Is there a cap on how many courses I can retake over the summer?",
     "relevant": [{"source": "academic-rules-handbook-jun-2026.pdf", "section": "6.6"},
                  {"source": "academic-rules-handbook-jun-2026.pdf", "section": "1.19"}],
     "expect": "2"},
    {"id": "h04", "type": "batch-b", "hard": True,
     "question": "How many library books can an undergraduate borrow at a time, and for how long?",
     "relevant": [{"source": "b02-library-borrowing-rules.md", "section": "2.1"}],
     "expect": "three"},
    {"id": "h05", "type": "batch-b", "hard": True,
     "question": "What is the fine for returning a library book late?",
     "relevant": [{"source": "b02-library-borrowing-rules.md", "section": "3.1"}],
     "expect": "50"},
    {"id": "h06", "type": "batch-b", "hard": True,
     "question": "When are the Fall 2026 midterm examinations held?",
     "relevant": [{"source": "b01-midterm-exam-notice-2026.md", "section": "1.1"}],
     "expect": "week 8"},
    {"id": "h07", "type": "batch-b", "hard": True,
     "question": "Can I keep my smart watch with me during a midterm paper?",
     "relevant": [{"source": "b01-midterm-exam-notice-2026.md", "section": "2.2"}],
     "expect": "unfair means"},
    {"id": "h08", "type": "batch-b", "hard": True,
     "question": "How many guests may a graduate bring to the 2026 convocation?",
     "relevant": [{"source": "c01-convocation-notice.pdf", "section": "Convocation Notice 2026"}],
     "expect": "two"},
    {"id": "h09", "type": "batch-b", "hard": True,
     "question": "Who can borrow a laptop under the laptop loan scheme, and what is the charge for returning it late?",
     "relevant": [{"source": "c02-laptop-loan-scheme.pdf", "section": "Laptop Loan Scheme"}],
     "expect": "200"},
]


# Pages for the two Assignment 02 questions whose heading is not a chunk label in the index
# (both documented in docs/PIPELINE.md, "What we could not recover"): g11's table is on
# p.19 of the 2023-24 annual report (extraction loss); g12's "Eligibility criteria" heading
# was OCR'd as body text and sits in the chunk labelled "Objectives" on p.1.
PAGE_OVERRIDES = {
    ("g11", "annual-report-2023-24.pdf"): [19],
    ("g12", "faculty-entrepreneurship-and-technical-start-ups-policy.pdf"): [1],
}


def main() -> int:
    index = json.loads((HERE / "index_sections.json").read_text(encoding="utf-8"))
    human = yaml.safe_load((HERE / "golden.yaml").read_text(encoding="utf-8"))["questions"]
    rows = []
    for q in human:
        rows.append({**q, "origin": "human", "reviewed": "group (written by hand, Assignment 02)",
                     "hard": q.get("type") in ("version", "exact", "injection")})
    for q in SYNTHETIC:
        rows.append({**q, "origin": "synthetic", "reviewed": False})

    unresolved = []
    for r in rows:
        r.setdefault("must_abstain", False)
        r["answerable"] = not r["must_abstain"]
        for rel in r.get("relevant", []):
            hits = [m for m in index if m["source"] == rel["source"]
                    and section_matches(str(rel["section"]), str(m["section"]))]
            rel["doc_id"] = hits[0]["doc_id"] if hits else Path(rel["source"]).stem
            rel["pages"] = sorted({int(m["page"]) for m in hits if m.get("page") is not None})
            override = PAGE_OVERRIDES.get((r["id"], rel["source"]))
            if override and not rel["pages"]:
                rel["pages"], rel["page_source"] = override, "docs/PIPELINE.md (A2 extraction notes)"
            if not rel["pages"]:
                unresolved.append(f"{r['id']}: {rel['source']} / {rel['section']}")

    out = HERE / "golden.jsonl"
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = len(rows)
    ans = sum(r["answerable"] for r in rows)
    print(f"wrote {out.name}: {n} questions | answerable {ans} | unanswerable {n - ans} | "
          f"hard {sum(bool(r['hard']) for r in rows)} | human {sum(r['origin'] == 'human' for r in rows)} "
          f"| synthetic {sum(r['origin'] == 'synthetic' for r in rows)}")
    if unresolved:
        print("clause not found in the index (no page recorded):")
        for u in unresolved:
            print("  " + u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
