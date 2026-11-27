# RAHBAR live-query coverage: PASS

- golden: `eval/golden.jsonl` (34 questions)
- live: `eval/results/live/live-20261127T110927Z.json` (40 queries: 28 in-domain, 12 off-topic)
- cosine threshold: 0.7; required in-domain share: 0.85
- in-domain covered: 25/28 = **0.8929**
- off-topic covered: 0.0833 (expected to be low)
- score stats: {'in_domain_min': 0.5795, 'in_domain_mean': 0.8374, 'in_domain_max': 0.9771, 'off_topic_min': 0.4521, 'off_topic_mean': 0.5497, 'off_topic_max': 0.701}

## Uncovered in-domain queries by topic

| topic | ids |
|---|---|
| lab access | l25 |
| scholarships | l28 |
| transcript | l26 |

| id | query | best golden | score |
|---|---|---|---:|
| l25 | What are the computer lab opening hours? | g12 | 0.5795 |
| l26 | How do I officially request my transcript? | i01 | 0.6089 |
| l28 | What scholarships can students apply for? | a01 | 0.6744 |
