# RAHBAR release gate: FAIL

- candidate: `/results/ragops-20261127T163847Z-gate.json` — collection None (None chunks)
- baseline: `/app/eval/baseline-a3.json` — collection rahbar (1032 chunks)
- config: `/etc/rahbar-gate/gate.yaml`
- generated: 20261127T165736Z

| rule | level | metric | baseline | candidate | delta | requirement | result |
|---|---|---|---:|---:|---:|---|---|
| module-paraphrase | module | paraphrase_mean_cosine | 0.7864 | — | — | >= 0.7864 (baseline - 0.02) | **FAIL** |
| module-gap | module | gap | 0.3264 | — | — | >= 0.3264 (baseline - 0.02) | **FAIL** |
| module-determinism | module | determinism_max_abs_diff | 0.0000 | — | — | <= 0.001 | **FAIL** |
| component-recall3 | component | recall@3 | 0.9107 | — | — | >= 0.9107 (baseline - 0.05) | **FAIL** |
| component-recall5 | component | recall@5 | 0.9643 | — | — | >= 0.9643 (baseline - 0.02) | **FAIL** |
| component-mrr | component | mrr | 0.8304 | — | — | >= 0.8304 (baseline - 0.03) | **FAIL** |
| component-ndcg5 | component | ndcg@5 | 0.8383 | — | — | >= 0.8383 (baseline - 0.03) | **FAIL** |
| component-typos-recall5 | component | typos.recall@5 | 0.9286 | — | — | >= 0.9286 (baseline - 0.03) | **FAIL** |
| component-typos-mrr | component | typos.mrr | 0.8393 | — | — | >= 0.8393 (baseline - 0.03) | **FAIL** |
| e2e-faithfulness | end_to_end | faithfulness | 1.0000 | — | — | >= 0.95 and >= 1.0000 (baseline - 0.05) | **FAIL** |
| e2e-abstention | end_to_end | abstention_correct_unanswerable | 0.8333 | — | — | >= 0.83 | **FAIL** |
| e2e-false-abstention | end_to_end | false_abstention_answerable | 0.0714 | — | — | <= 0.12 and <= 0.0714 (baseline + 0.05) | **FAIL** |
| e2e-citations | end_to_end | citation_validity_in_retrieved | 1.0000 | — | — | >= 0.98 and >= 1.0000 (baseline - 0.02) | **FAIL** |
| e2e-latency-p95 | end_to_end | latency_p95_ms | 13671.5350 | — | — | <= 20000 and <= 13671.5350 (baseline x 1.60) | **FAIL** |

## Failures

- compatibility: golden sets differ: baseline 34 questions, candidate None questions
- compatibility: golden question ids differ: missing in candidate ['a01', 'a02', 'a03', 'a04', 'a05', 'a06'], extra in candidate []
- compatibility: embedding model changed: baseline 'nomic-embed-text', candidate None; compare inside one pin only
- compatibility: embedding version missing from a result (traces not mounted?)
- compatibility: candidate collection not recorded (no trace to identify what was tested)
- module-paraphrase: metric not measured in the candidate
- module-gap: metric not measured in the candidate
- module-determinism: metric not measured in the candidate
- component-recall3: metric not measured in the candidate
- component-recall5: metric not measured in the candidate
- component-mrr: metric not measured in the candidate
- component-ndcg5: metric not measured in the candidate
- component-typos-recall5: metric not measured in the candidate
- component-typos-mrr: metric not measured in the candidate
- e2e-faithfulness: metric not measured in the candidate
- e2e-abstention: metric not measured in the candidate
- e2e-false-abstention: metric not measured in the candidate
- e2e-citations: metric not measured in the candidate
- e2e-latency-p95: metric not measured in the candidate
