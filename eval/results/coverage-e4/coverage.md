# RAHBAR live-query coverage: PASS

- golden: `eval/golden-e4.jsonl` (42 questions)
- live: `eval/results/live/live-20261127T110927Z.json` (40 queries: 28 in-domain, 12 off-topic)
- cosine threshold: 0.7; required in-domain share: 0.85
- in-domain covered: 28/28 = **1.0**
- off-topic covered: 0.0833 (expected to be low)
- score stats: {'in_domain_min': 0.7469, 'in_domain_mean': 0.8964, 'in_domain_max': 1.0, 'off_topic_min': 0.4521, 'off_topic_mean': 0.5742, 'off_topic_max': 0.701}

## Uncovered in-domain queries by topic

| topic | ids |
|---|---|

| id | query | best golden | score |
|---|---|---|---:|
