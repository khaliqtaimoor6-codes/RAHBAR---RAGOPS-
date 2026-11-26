# RAHBAR offline suite 20261126T104001Z (re-judged)

collection: {'name': 'rahbar', 'index_id': 'f4c2ff9a3277', 'indexed_at': '2026-11-25T19:53:56Z', 'embed_model': 'nomic-embed-text', 'chunk_size': 150, 'chunk_overlap': 30, 'chunks': 1032}
golden: {'file': 'golden.jsonl', 'questions': 34, 'answerable': 28, 'unanswerable': 6, 'hard': 16, 'human': 21, 'synthetic': 13}

| level | metric | run 1 | run 2 | difference |
|---|---|---|---|---|
| module | paraphrase_mean_cosine | 0.7864 | 0.7864 | 0.0 |
| module | unrelated_mean_cosine | 0.46 | 0.46 | 0.0 |
| module | gap | 0.3264 | 0.3264 | 0.0 |
| module | ms_per_chunk_single | 41.9 | 48.5 | 6.6 |
| module | determinism_max_abs_diff | 0.0 | 0.0 | 0.0 |
| component.clean | recall@3 | 0.9107 | 0.9107 | 0.0 |
| component.clean | recall@5 | 0.9643 | 0.9643 | 0.0 |
| component.clean | mrr | 0.8304 | 0.8304 | 0.0 |
| component.clean | ndcg@5 | 0.8383 | 0.8383 | 0.0 |
| component.typos | recall@5 | 0.9286 | 0.9286 | 0.0 |
| component.typos | mrr | 0.8393 | 0.8393 | 0.0 |
| end_to_end | faithfulness | 1.0 | 1.0 | 0.0 |
| end_to_end | abstention_correct_unanswerable | 0.8333 | 0.8333 | 0.0 |
| end_to_end | false_abstention_answerable | 0.0357 | 0.1071 | 0.0714 |
| end_to_end | citation_validity_in_retrieved | 1.0 | 1.0 | 0.0 |
| end_to_end | citation_validity_gt_doc | 0.8704 | 0.8733 | 0.0029 |
| end_to_end | expected_string_hit | 0.8571 | 0.7143 | -0.1428 |
| end_to_end | latency_p50_ms | 8190.75 | 8934.4 | 743.65 |
| end_to_end | latency_p95_ms | 13681.11 | 13661.96 | -19.15 |
