"""How often does the LLM faithfulness judge agree with us? (Part B, end-to-end level)

The suite writes eval/results/judge-hand-labels-<ts>.csv with the judge's verdict for up to
12 answers. A group member reads each answer against its context
(`kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show <trace_id>`) and
writes `yes` (every claim supported) or `no` in `human_label`. Then:

    python eval/judge_agreement.py eval/results/judge-hand-labels-<ts>.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1])
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    labelled = [r for r in rows if r["human_label"].strip().lower() in ("yes", "no")]
    if len(labelled) < 8:
        print(f"{len(labelled)} answers labelled by hand; the assignment asks for at least 8")
        return 1
    agree = sum((r["human_label"].strip().lower() == "yes") == (r["judge_supported"] == "True")
                for r in labelled)
    print(f"labelled by hand: {len(labelled)}   judge agrees: {agree}/{len(labelled)} "
          f"= {agree / len(labelled):.0%}")
    for r in labelled:
        mark = "agree" if (r["human_label"].strip().lower() == "yes") == (r["judge_supported"] == "True") else "DISAGREE"
        print(f"  {r['id']:5} judge={r['judge_supported']:5} human={r['human_label']:4} {mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
