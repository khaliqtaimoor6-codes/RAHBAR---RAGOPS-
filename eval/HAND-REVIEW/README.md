# Human-only review worksheets

These are blank worksheets. They contain no human decisions.

1. `synthetic-ali.csv` / `synthetic-taimoor.csv`: fill `reviewed_by`, `decision` (`ok`/`fix`) and `notes` after reading the exact excerpt in the matching `.md` file.
2. `judge-ali.csv` / `judge-taimoor.csv`: fill `human_label` (`yes`/`no`) after reading the exact context in the matching `.md` file. Leave `judge_supported` alone.
3. Once both members have filled their own CSVs, merge the rows back into `eval/build_golden.py` (`reviewed`) and `eval/results/suite/judge-hand-labels-20261128T115331Z.csv` (`human_label`), then run `python eval/build_golden.py` and `python eval/judge_agreement.py <csv>`.

Ali: 7 synthetic questions + 6 judge labels. Taimoor: 6 synthetic questions + 6 judge labels. No answer is prefilled.
