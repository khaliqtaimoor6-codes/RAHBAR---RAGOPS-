#!/usr/bin/env python3
"""Build blank human-review worksheets for the two assignment hand tasks."""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "HAND-REVIEW"
OUT.mkdir(parents=True, exist_ok=True)

ALI_SYNTHETIC = ["a03", "h01", "h03", "h05", "h07", "h09", "h08"]
TAIMOOR_SYNTHETIC = ["a04", "a05", "a06", "h02", "h04", "h06"]
ALI_JUDGE = ["g01", "g02", "g03", "g04", "g05", "g06"]
TAIMOOR_JUDGE = ["g07", "g08", "g09", "g10", "g12", "v01"]


def extracted() -> dict[str, dict]:
    raw = subprocess.check_output(
        ["kubectl", "-n", "rahbar", "exec", "lake-shell", "--", "python", "-c",
         "import json,glob;print(json.dumps({p.split('/')[-1][:-5]:json.load(open(p)) for p in glob.glob('/data/lake/extracted/*.json')}))"],
        text=True)
    return json.loads(raw)


def source_excerpt(doc: dict, source: str, section: str) -> str:
    pages = doc.get("pages", [])
    hits = []
    for page in pages:
        text = page.get("text", "")
        if section and section.lower() in text.lower():
            hits.append(f"p{page.get('page')}: {text.strip()}")
    if hits:
        return "\n\n".join(hits[:2])
    # Fallback: first 1200 chars of matching source
    return "\n\n".join(f"p{p.get('page')}: {p.get('text','').strip()[:1200]}"
                       for p in pages[:2])


def load_synthetic() -> dict[str, dict]:
    ns: dict = {"__file__": str(ROOT / "eval" / "build_golden.py"), "__name__": "build_golden_review"}
    src = (ROOT / "eval" / "build_golden.py").read_text()
    exec(compile(src, "build_golden.py", "exec"), ns)
    return {q["id"]: q for q in ns["SYNTHETIC"]}


def write_synthetic(name: str, ids: list[str], syn: dict[str, dict], docs: dict[str, dict]) -> None:
    rows = []
    for qid in ids:
        q = syn[qid]
        rel = q.get("relevant") or []
        if rel:
            doc = docs.get(Path(rel[0]["source"]).stem, {})
            excerpt = source_excerpt(doc, rel[0]["source"], str(rel[0].get("section", "")))
            evidence = " | ".join(f"{r['source']} / {r.get('section','')}" for r in rel)
        else:
            excerpt = "(none — this is an abstain question; check that no document answers it)"
            evidence = "(no relevant document declared)"
        rows.append({
            "id": qid,
            "question": q["question"],
            "type": q.get("type", ""),
            "hard": q.get("hard", False),
            "declared_evidence": evidence,
            "expect": q.get("expect", ""),
            "must_abstain": q.get("must_abstain", False),
            "source_excerpt": excerpt,
            "reviewed_by": "",
            "decision": "",
            "notes": "",
        })
    with (OUT / f"synthetic-{name}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    md = [f"# Synthetic golden-question review — {name}", "",
          "For each row: read the exact source excerpt, decide whether the question and "
          "expected answer are correct, then fill `reviewed_by`, `decision` (`ok` / `fix`) "
          "and `notes` in the CSV. Do not change `judge_supported` in the judge worksheet.", ""]
    for r in rows:
        md += [f"## {r['id']} — {r['question']}", "",
               f"- type: {r['type']}; hard: {r['hard']}; must_abstain: {r['must_abstain']}",
               f"- declared evidence: {r['declared_evidence']}",
               f"- expect: {r['expect'] or '(abstain)' }",
               "- source excerpt:", "```text", r["source_excerpt"], "```", ""]
    (OUT / f"synthetic-{name}.md").write_text("\n".join(md), encoding="utf-8")


def load_traces() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in (ROOT / "traces" / "cluster").glob("*.jsonl"):
        for line in p.open(encoding="utf-8", errors="replace"):
            if '"trace_id"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("trace_id"):
                out[str(d["trace_id"])] = d
    return out


def write_judge(name: str, ids: list[str], traces: dict[str, dict]) -> None:
    src = ROOT / "eval" / "results" / "suite" / "judge-hand-labels-20261128T115331Z.csv"
    rows_all = {r["id"]: r for r in csv.DictReader(src.open(encoding="utf-8"))}
    rows = []
    md = [f"# Faithfulness judge hand-label review — {name}", "",
          "For each row: read the exact context the model saw and decide whether **every** "
          "claim in the answer is supported. Write `yes` or `no` in `human_label` in the CSV. "
          "Do not edit `judge_supported`.", ""]
    for qid in ids:
        r = rows_all[qid]
        d = traces.get(r["trace_id"], {})
        ctx = d.get("context") or []
        blocks = [f"[{c.get('rank')}] {c.get('source')} — {c.get('section')} "
                  f"(p.{c.get('page')}, v={c.get('doc_version')})\n{c.get('text','')}"
                  for c in ctx]
        excerpt = "\n\n".join(blocks)
        rows.append({
            "id": qid,
            "trace_id": r["trace_id"],
            "question": r["question"],
            "answer": r["answer"],
            "judge_supported": r["judge_supported"],
            "human_label": "",
            "notes": "",
        })
        md += [f"## {qid} — {r['question']}", "",
               f"- answer: {r['answer']}",
               f"- judge_supported: {r['judge_supported']} (do not edit)",
               "- exact context:", "```text", excerpt, "```", ""]
    with (OUT / f"judge-{name}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT / f"judge-{name}.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    docs = extracted()
    syn = load_synthetic()
    traces = load_traces()
    write_synthetic("ali", ALI_SYNTHETIC, syn, docs)
    write_synthetic("taimoor", TAIMOOR_SYNTHETIC, syn, docs)
    write_judge("ali", ALI_JUDGE, traces)
    write_judge("taimoor", TAIMOOR_JUDGE, traces)
    (OUT / "README.md").write_text("\n".join([
        "# Human-only review worksheets", "",
        "These are blank worksheets. They contain no human decisions.", "",
        "1. `synthetic-ali.csv` / `synthetic-taimoor.csv`: fill `reviewed_by`, `decision` "
        "(`ok`/`fix`) and `notes` after reading the exact excerpt in the matching `.md` file.",
        "2. `judge-ali.csv` / `judge-taimoor.csv`: fill `human_label` (`yes`/`no`) after "
        "reading the exact context in the matching `.md` file. Leave `judge_supported` alone.",
        "3. Once both members have filled their own CSVs, merge the rows back into "
        "`eval/build_golden.py` (`reviewed`) and "
        "`eval/results/suite/judge-hand-labels-20261128T115331Z.csv` (`human_label`), then "
        "run `python eval/build_golden.py` and `python eval/judge_agreement.py <csv>`.", "",
        "Ali: 7 synthetic questions + 6 judge labels. Taimoor: 6 synthetic questions + "
        "6 judge labels. No answer is prefilled.", "",
    ]), encoding="utf-8")
    print("wrote worksheets to", OUT)


if __name__ == "__main__":
    main()
