"""Unit tests for the C2 release gate (no cluster, no network).

Run:  python -m pytest eval/tests -q
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import gate  # noqa: E402  (sibling module, path set above)

BASELINE_METRICS = {
    "module": {
        "paraphrase_mean_cosine": 0.7864, "unrelated_mean_cosine": 0.46,
        "gap": 0.3264, "determinism_max_abs_diff": 0.0,
    },
    "component": {
        "clean": {"recall@3": 0.9107, "recall@5": 0.9643, "mrr": 0.8304, "ndcg@5": 0.8383},
        "typos": {"recall@5": 0.9286, "mrr": 0.8393},
    },
    "end_to_end": {
        "faithfulness": 1.0, "abstention_correct_unanswerable": 0.8333,
        "false_abstention_answerable": 0.0715, "citation_validity_in_retrieved": 1.0,
        "latency_p95_ms": 13671.5,
    },
}


def make_result(*, changes: dict | None = None, questions: int = 34,
                embed_model: str = "nomic-embed-text", version: str = "emb@1",
                collection: str | None = "rahbar") -> dict:
    metrics = copy.deepcopy(BASELINE_METRICS)
    for section, values in (changes or {}).items():
        if isinstance(values, dict) and section in metrics:
            for key, value in values.items():
                if isinstance(value, dict) and key in metrics[section] and isinstance(metrics[section][key], dict):
                    metrics[section][key].update(value)
                else:
                    metrics[section][key] = value
    ids = [f"q{i:02d}" for i in range(questions)]
    run = {
        **copy.deepcopy(metrics),
        "answers": [{"id": qid, "answer": "ok"} for qid in ids],
    }
    return {
        "timestamp": "20261126T000000Z",
        "embed_model": embed_model,
        "embedding_version": version,
        "collection": {"name": collection, "chunks": 1000} if collection else None,
        "golden": {"questions": questions, "file": "golden.jsonl"},
        "runs": [run],
    }


def write(path: Path, result: dict) -> Path:
    path.write_text(json.dumps(result), encoding="utf-8")
    return path


def run_gate(tmp_path: Path, candidate: dict, config: Path | None = None) -> gate.GateResult:
    baseline = write(tmp_path / "baseline.json", make_result())
    cand = write(tmp_path / "candidate.json", candidate)
    return gate.evaluate(cand, baseline, config or gate.DEFAULT_CONFIG,
                         tmp_path / "gate-report")


def failing_ids(result: gate.GateResult) -> set[str]:
    return {check["id"] for check in result.checks if not check["passed"]}


def test_identical_candidate_passes(tmp_path):
    result = run_gate(tmp_path, make_result(collection="rahbar-cand-cs300"))
    assert result.passed, result.failures
    assert not failing_ids(result)
    report = json.loads((tmp_path / "gate-report.json").read_text())
    assert report["gate"] == "pass"


def test_recall_drop_above_two_points_fails(tmp_path):
    result = run_gate(tmp_path, make_result(changes={
        "component": {"clean": {"recall@5": 0.93}},
    }))
    assert not result.passed
    assert "component-recall5" in failing_ids(result)
    assert "drop" in next(c["message"] for c in result.checks if c["id"] == "component-recall5")


def test_small_recall_drop_within_two_points_passes(tmp_path):
    result = run_gate(tmp_path, make_result(changes={
        "component": {"clean": {"recall@5": 0.95}},
    }))
    assert result.passed, result.failures


def test_typo_recall_and_mrr_are_checked(tmp_path):
    result = run_gate(tmp_path, make_result(changes={
        "component": {"typos": {"recall@5": 0.87, "mrr": 0.78}},
    }))
    assert {"component-typos-recall5", "component-typos-mrr"} <= failing_ids(result)


def test_faithfulness_below_min_fails(tmp_path):
    result = run_gate(tmp_path, make_result(changes={
        "end_to_end": {"faithfulness": 0.92},
    }))
    assert "e2e-faithfulness" in failing_ids(result)


def test_abstention_below_min_fails(tmp_path):
    result = run_gate(tmp_path, make_result(changes={
        "end_to_end": {"abstention_correct_unanswerable": 0.66},
    }))
    assert "e2e-abstention" in failing_ids(result)


def test_false_abstention_rise_fails(tmp_path):
    result = run_gate(tmp_path, make_result(changes={
        "end_to_end": {"false_abstention_answerable": 0.20},
    }))
    assert "e2e-false-abstention" in failing_ids(result)


def test_latency_cap_fails(tmp_path):
    result = run_gate(tmp_path, make_result(changes={
        "end_to_end": {"latency_p95_ms": 25000},
    }))
    assert "e2e-latency-p95" in failing_ids(result)


def test_unmeasured_metric_fails(tmp_path):
    candidate = make_result()
    del candidate["runs"][0]["end_to_end"]["faithfulness"]
    assert "e2e-faithfulness" in failing_ids(run_gate(tmp_path, candidate))


def test_golden_mismatch_fails(tmp_path):
    result = run_gate(tmp_path, make_result(questions=33))
    assert any("golden sets differ" in f or "question ids differ" in f for f in result.failures)


def test_embedding_change_fails(tmp_path):
    result = run_gate(tmp_path, make_result(embed_model="other-embed"))
    assert any("embedding model changed" in f for f in result.failures)
    result = run_gate(tmp_path, make_result(version="emb@2"))
    assert any("embedding version changed" in f for f in result.failures)


def test_missing_collection_fails(tmp_path):
    assert any("collection not recorded" in f
               for f in run_gate(tmp_path, make_result(collection=None)).failures)


def test_real_baseline_passes_against_itself(tmp_path):
    baseline = gate.DEFAULT_BASELINE
    result = gate.evaluate(baseline, baseline, gate.DEFAULT_CONFIG, tmp_path / "self-gate")
    assert result.passed, result.failures


def test_config_mirrors_the_configmap():
    repo = yaml.safe_load(gate.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    cm_path = HERE.parent / "k8s/base/gate-config.yaml"
    cm = yaml.safe_load(cm_path.read_text(encoding="utf-8"))
    assert repo == yaml.safe_load(cm["data"]["gate.yaml"])


def test_unknown_config_version_is_bad_input(tmp_path):
    config = tmp_path / "bad.yaml"
    config.write_text("version: 99\nrules: []\n", encoding="utf-8")
    candidate = write(tmp_path / "c.json", make_result())
    with pytest.raises(ValueError, match="unsupported gate config version"):
        gate.evaluate(candidate, candidate, config)


def test_cli_and_suite_gate_only_exit_codes(tmp_path, capsys):
    candidate = write(tmp_path / "c.json", make_result())
    baseline = write(tmp_path / "b.json", make_result())
    assert gate.main(["--candidate", str(candidate), "--baseline", str(baseline),
                      "--config", str(gate.DEFAULT_CONFIG)]) == 0
    assert "GATE PASSED" in capsys.readouterr().out

    bad = write(tmp_path / "bad.json", make_result(changes={
        "component": {"clean": {"recall@5": 0.5}},
    }))
    assert gate.main(["--candidate", str(bad), "--baseline", str(baseline),
                      "--config", str(gate.DEFAULT_CONFIG)]) == 1
    assert "GATE FAILED" in capsys.readouterr().out

    import ragops_suite
    assert ragops_suite.main(["--gate-only", str(candidate), "--gate-baseline", str(baseline),
                              "--gate-config", str(gate.DEFAULT_CONFIG)]) == 0
