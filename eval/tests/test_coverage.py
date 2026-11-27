"""Unit tests for the E2/E4 coverage checker (stub embedder, no Ollama)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import coverage  # noqa: E402


class FakeEmbedder:
    """First call embeds golden questions, second call embeds live queries."""

    def __init__(self, golden_vector: list[float], live_vector: list[float]) -> None:
        self.golden_vector = golden_vector
        self.live_vector = live_vector
        self.calls = 0

    def embed(self, texts: list[str], prefix: str) -> list[list[float]]:
        self.calls += 1
        vector = self.golden_vector if self.calls == 1 else self.live_vector
        return [list(vector) for _ in texts]


def write_fixtures(tmp_path: Path) -> tuple[Path, Path]:
    golden = tmp_path / "golden.jsonl"
    golden.write_text(
        '\n'.join(json.dumps({"id": f"g{i}", "question": q}) for i, q in enumerate(
            ["CGPA warning rule", "library borrowing limit"])) + '\n', encoding="utf-8")
    live = tmp_path / "live.json"
    live.write_text(json.dumps({"results": [
        {"id": "l1", "query": "minimum cgpa to avoid warning", "topic": "warning", "in_domain": True},
        {"id": "l2", "query": "how many library books", "topic": "library", "in_domain": True},
        {"id": "o1", "query": "weather tomorrow", "topic": "weather", "in_domain": False},
    ]}), encoding="utf-8")
    return golden, live


def make_args(golden: Path, live: Path, out: Path, **overrides):
    from argparse import Namespace
    values = {"live": str(live), "golden": str(golden), "ollama": "http://x",
              "embed_model": "nomic-embed-text", "threshold": 0.70, "min_share": 0.85,
              "out": str(out)}
    values.update(overrides)
    return Namespace(**values)


def test_all_covered_passes(tmp_path):
    golden, live = write_fixtures(tmp_path)
    result = coverage.run(make_args(golden, live, tmp_path / "cov"),
                          embedder=FakeEmbedder([1.0, 0.0], [1.0, 0.0]))
    assert result["passed"]
    assert result["in_domain_share"] == 1.0
    assert result["covered_in_domain"] == 2
    assert result["uncovered"] == []
    assert (tmp_path / "cov" / "coverage.md").exists()


def test_none_covered_fails_and_groups_by_topic(tmp_path):
    golden, live = write_fixtures(tmp_path)
    result = coverage.run(make_args(golden, live, tmp_path / "cov"),
                          embedder=FakeEmbedder([1.0, 0.0], [0.0, 1.0]))
    assert not result["passed"]
    assert result["in_domain_share"] == 0.0
    assert result["uncovered_by_topic"] == {"library": ["l2"], "warning": ["l1"]}
    assert all(row["best_golden"] in {"g0", "g1"} for row in result["rows"])


def test_main_exit_code_and_off_topic_reporting(tmp_path, monkeypatch):
    golden, live = write_fixtures(tmp_path)
    monkeypatch.setattr(coverage, "Embedder",
                        lambda url, model: FakeEmbedder([1.0, 0.0], [0.0, 1.0]))
    code = coverage.main(["--live", str(live), "--golden", str(golden),
                          "--out", str(tmp_path / "cov")])
    assert code == 1
    saved = json.loads((tmp_path / "cov" / "coverage.json").read_text())
    assert saved["off_topic"] == 1
    assert saved["off_topic_share"] == 0.0
    assert "Uncovered in-domain queries" in (tmp_path / "cov" / "coverage.md").read_text()
