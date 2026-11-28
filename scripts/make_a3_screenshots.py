#!/usr/bin/env python3
"""Render command/output transcripts into terminal-style PNGs for the report appendix."""
from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
W, PAD, LH = 1280, 24, 20


def wrap(text: str, width: int = 118) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        while len(line) > width:
            cut = line.rfind(" ", 0, width)
            cut = cut if cut > width // 2 else width
            out.append(line[:cut])
            line = "    " + line[cut:].lstrip()
        out.append(line)
    return out


def shot(label: str, command: str, body: str, name: str) -> None:
    lines = [f"$ {command}"] + wrap(body)
    h = PAD * 2 + LH * (len(lines) + 2)
    img = Image.new("RGB", (W, h), "#0d1117")
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 15)
    bold = ImageFont.truetype(FONT, 17)
    d.rectangle((0, 0, W, 34), fill="#161b22")
    d.text((PAD, 8), f"RAHBAR · {label}", font=bold, fill="#58a6ff")
    y = 52
    for line in lines:
        d.text((PAD, y), line, font=font, fill="#c9d1d9")
        y += LH
    SHOTS.mkdir(parents=True, exist_ok=True)
    img.save(SHOTS / name)
    print("wrote", SHOTS / name, img.size)


def main() -> int:
    spec = [
        ("A1", "kubectl -n rahbar exec lake-shell -- python -m pipeline.ingest --report 20261127T140208Z",
         "evidence-verification.txt", "A1-verification.png"),
        ("A2", "kubectl -n rahbar logs job/ingest-rerun-unchanged --tail=25",
         "evidence-zero-reembed.txt", "A2-zero-reembed.png"),
        ("B", "cat eval/results/suite/ragops-20261127T163847Z.md",
         "evidence-suite.md", "B-suite.png"),
        ("C fail", "cat eval/results/suite/ragops-20261127T123310Z-gate.md",
         "evidence-gate-fail.md", "C-gate-fail.png"),
        ("C pass", "kubectl -n rahbar logs job/eval-gate",
         "evidence-gate-pass.txt", "C-gate-pass.png"),
        ("D1", "kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show 599580d943184022a978c9fb11743a61",
         "evidence-trace.txt", "D1-trace.png"),
        ("D2", "cat docs/evidence/a3/D2-trace-show-answered.txt",
         "evidence-trace-show.txt", "D2-trace-show.png"),
        ("E before", "python eval/coverage.py --live eval/results/live/live-20261127T110927Z.json --golden eval/golden.jsonl --out eval/results/coverage.json",
         "evidence-coverage-before.md", "E-coverage-before.png"),
        ("E after", "python eval/coverage.py --live eval/results/live/live-20261127T110927Z.json --golden eval/golden-e4.jsonl --out eval/results/coverage-e4",
         "evidence-coverage-after.md", "E-coverage-after.png"),
        ("F1", "kubectl -n rahbar get all,pvc,configmap,cronjob,job",
         "evidence-get-all.txt", "F1-get-all.png"),
        ("F2", "cat docs/evidence/a3/F2-gate-config-change.txt",
         "evidence-f2.txt", "F2-config-change.png"),
        ("F3", "cat docs/evidence/a3/F3-rollout-topk6.txt docs/evidence/a3/F3-rollback-topk6.txt",
         "evidence-f3.txt", "F3-rollout-undo.png"),
        ("F4", "kubectl -n rahbar logs job/ingest-cand-topk6; kubectl -n rahbar logs job/eval-candidate",
         "evidence-completed-jobs.txt", "F4-completed-jobs.png"),
    ]
    for label, cmd, path, name in spec:
        p = ROOT / "docs" / "report" / "assets" / path
        shot(label, cmd, p.read_text(encoding="utf-8", errors="replace"), name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
