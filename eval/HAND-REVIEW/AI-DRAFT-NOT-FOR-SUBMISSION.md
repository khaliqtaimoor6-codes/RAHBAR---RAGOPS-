# AI draft — NOT a human review and NOT for submission

This file is an AI-generated draft only. It does **not** satisfy the assignment requirement
that at least 8 synthetic questions are reviewed by hand and at least 8 judge verdicts are
labelled by hand. No member has reviewed or labelled anything here.

Ali and Taimoor must independently check the exact evidence in the corresponding
`synthetic-*.md` / `judge-*.md` files, then enter their own decisions in the official CSVs.
If they agree with a suggestion, they must still enter it themselves and take responsibility
for it. Do not copy these values into the official files without human verification.

## Synthetic golden-question review — suggestions

### Ali

| id | suggested `decision` | suggested `notes` |
|---|---|---|
| a03 | ok | No campus housing rule about pets; keyword hits are false positives such as “competent”. Abstain is correct. |
| h01 | ok | Rule 5.6 says CGPA below 2.00 for 3 consecutive semesters closes admission; `expect: closed` is supported. |
| h03 | ok | Rule 6.6 allows a maximum of 2 repeat courses in summer; `expect: 2` is supported. |
| h05 | ok | Rule 3.1 charges 50 rupees per day per late library book; `expect: 50` is supported. |
| h07 | ok | Rule 2.2 treats possession of a smart watch/device at the desk as unfair means; `expect: unfair means` is supported. |
| h09 | ok | Laptop scheme charges 200 rupees per day for late return; `expect: 200` is supported. |
| h08 | ok | Convocation notice says each graduate may bring two guests; `expect: two` is supported. |

### Taimoor

| id | suggested `decision` | suggested `notes` |
|---|---|---|
| a04 | ok | Cafeteria is mentioned as a facility, but no meal price appears in the indexed corpus; demo c03 was quarantined. Abstain is correct. |
| a05 | ok | No document covers the 2022 FIFA World Cup. Abstain is correct. |
| a06 | ok | No monthly student car-parking fee is stated in the corpus. Abstain is correct. |
| h02 | ok | Rule 5.4 gives 2.00 and rule 5.6 gives closure after three semesters; `expect: 2.00` is supported. |
| h04 | ok | Rule 2.1 says three books at a time for fourteen days; `expect: three` is supported. |
| h06 | ok | Rule 1.1 says Fall 2026 midterms are in week 8; `expect: week 8` is supported. |

## Faithfulness judge hand-label — suggestions

All 12 rows have `judge_supported = True`. The AI draft suggests:

### Ali

| id | suggested `human_label` | reason |
|---|---|---|
| g01 | yes | Rule 5.4 directly states minimum CGPA 2.00 to avoid warning. |
| g02 | yes | Rules 5.6 and 3.28 directly state admission closes after three consecutive semesters below 2.00. |
| g03 | yes | Rule 4.3 directly states normal course load is 5 courses. |
| g04 | yes | Prospectus rule 19 and rule 1.19 state a maximum of 2 summer repeat courses. |
| g05 | yes | Rule 5.25 states rechecking fee is refunded if marks increase. |
| g06 | yes | Rule 6.2 prohibits ChatGPT/generative AI in labs unless the lab instructor explicitly allows it. |

### Taimoor

| id | suggested `human_label` | reason |
|---|---|---|
| g07 | yes | Fee page states admission fee Rs 30,000 and admission fee is non-refundable. |
| g08 | yes | Grade table lists B+ = 3.33. |
| g09 | yes | Rule 1.23 states maximum 6 years, extendable by one year with Statutory Bodies approval. |
| g10 | yes | Rule 7.3 states SGPA 4.00 with at least 30 credit hours for Rector’s List. |
| g12 | yes | ORIC policy eligibility says full-time faculty for more than 1 year. |
| v01 | yes | Rule 4.25 states withdrawal deadline is the last day of the makeup week. |

If both members independently confirm all 12 suggestions, the agreement result would be
**12/12 = 100%**. That number must not be reported until a human has actually entered the
labels and run `python eval/judge_agreement.py eval/results/suite/judge-hand-labels-20261128T115331Z.csv`.
