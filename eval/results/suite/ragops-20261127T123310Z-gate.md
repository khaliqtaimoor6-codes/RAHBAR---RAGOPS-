# RAHBAR release gate: FAIL

- candidate: `/results/ragops-20261127T123310Z.json` — collection rahbar-cand-cs300 (309 chunks)
- baseline: `/app/eval/baseline-a3.json` — collection rahbar (1032 chunks)
- config: `/etc/rahbar-gate/gate.yaml`
- generated: 20261127T125158Z

| rule | level | metric | baseline | candidate | delta | requirement | result |
|---|---|---|---:|---:|---:|---|---|
| module-paraphrase | module | paraphrase_mean_cosine | 0.7864 | 0.7865 | +0.0001 | >= 0.7864 (baseline - 0.02) | PASS |
| module-gap | module | gap | 0.3264 | 0.3263 | -0.0001 | >= 0.3264 (baseline - 0.02) | PASS |
| module-determinism | module | determinism_max_abs_diff | 0.0000 | 0.0000 | +0.0000 | <= 0.001 | PASS |
| component-recall3 | component | recall@3 | 0.9107 | 0.6071 | -0.3036 | >= 0.9107 (baseline - 0.05) | **FAIL** |
| component-recall5 | component | recall@5 | 0.9643 | 0.6964 | -0.2679 | >= 0.9643 (baseline - 0.02) | **FAIL** |
| component-mrr | component | mrr | 0.8304 | 0.5536 | -0.2768 | >= 0.8304 (baseline - 0.03) | **FAIL** |
| component-ndcg5 | component | ndcg@5 | 0.8383 | 0.5688 | -0.2695 | >= 0.8383 (baseline - 0.03) | **FAIL** |
| component-typos-recall5 | component | typos.recall@5 | 0.9286 | 0.6071 | -0.3215 | >= 0.9286 (baseline - 0.03) | **FAIL** |
| component-typos-mrr | component | typos.mrr | 0.8393 | 0.4911 | -0.3482 | >= 0.8393 (baseline - 0.03) | **FAIL** |
| e2e-faithfulness | end_to_end | faithfulness | 1.0000 | 1.0000 | +0.0000 | >= 0.95 and >= 1.0000 (baseline - 0.05) | PASS |
| e2e-abstention | end_to_end | abstention_correct_unanswerable | 0.8333 | 1.0000 | +0.1667 | >= 0.83 | PASS |
| e2e-false-abstention | end_to_end | false_abstention_answerable | 0.0714 | 0.9643 | +0.8929 | <= 0.12 and <= 0.0714 (baseline + 0.05) | **FAIL** |
| e2e-citations | end_to_end | citation_validity_in_retrieved | 1.0000 | 1.0000 | +0.0000 | >= 0.98 and >= 1.0000 (baseline - 0.02) | PASS |
| e2e-latency-p95 | end_to_end | latency_p95_ms | 13671.5350 | 33962.2700 | +20290.7350 | <= 20000 and <= 13671.5350 (baseline x 1.25) | **FAIL** |

## Failures

- component-recall3: drop 0.3036 > allowed 0.05
- component-recall5: drop 0.2679 > allowed 0.02
- component-mrr: drop 0.2768 > allowed 0.03
- component-ndcg5: drop 0.2695 > allowed 0.03
- component-typos-recall5: drop 0.3215 > allowed 0.03
- component-typos-mrr: drop 0.3482 > allowed 0.03
- e2e-false-abstention: 0.9643 > maximum 0.12; rise 0.8929 > allowed 0.05
- e2e-latency-p95: 33962.2700 > maximum 20000; rise to 33962.2700 > allowed 17089.4188
