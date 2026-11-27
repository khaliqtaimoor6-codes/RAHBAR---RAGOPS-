"""Unit tests for the E1 live-query driver (no cluster, stub client)."""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import live_queries  # noqa: E402


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self.payload = payload or {}
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self.payload


class FakeClient:
    def __init__(self, payloads: list[dict], status: int = 200) -> None:
        self.payloads = list(payloads)
        self.status = status
        self.calls: list[tuple[str, dict, dict]] = []

    def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
        self.calls.append((url, json, headers))
        payload = self.payloads.pop(0) if self.payloads else {}
        return FakeResponse(self.status, payload)


def make_args(tmp_path: Path, **overrides) -> Namespace:
    values = {"api": "http://rahbar.local", "queries": str(HERE / "live_queries.jsonl"),
              "out": str(tmp_path / "live"), "pace": 0, "limit": 0}
    values.update(overrides)
    return Namespace(**values)


def test_live_query_file_has_40_questions():
    rows = live_queries.load_queries(HERE / "live_queries.jsonl")
    assert len(rows) == 40
    assert sum(bool(r["in_domain"]) for r in rows) == 28
    assert sum(not r["in_domain"] for r in rows) == 12
    assert len({r["id"] for r in rows}) == 40


def test_load_queries_rejects_a_bad_row(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"id": "x", "query": "y"}\n', encoding="utf-8")
    try:
        live_queries.load_queries(path)
    except ValueError as exc:
        assert "topic" in str(exc)
    else:
        raise AssertionError("missing topic was accepted")


def test_run_writes_log_with_trace_ids(tmp_path):
    payload = {"trace_id": "abc123", "answered_from_context": True, "answer": "2.00",
               "citations": [{"source": "handbook", "page": 24}],
               "retrieved": [{"source": "handbook", "score": 0.81}], "cached": False}
    client = FakeClient([payload] * 40)
    result = live_queries.run(make_args(tmp_path), client=client)
    assert result["questions"] == 40
    assert result["errors"] == 0
    assert result["in_domain"] == 28 and result["off_topic"] == 12
    assert all(r["trace_id"] == "abc123" for r in result["results"])
    assert all(r["top_score"] == 0.81 for r in result["results"])
    assert all(c[2] == {"X-RAHBAR-Cache": "bypass"} for c in client.calls)
    files = list((tmp_path / "live").glob("live-*.json"))
    assert len(files) == 1
    saved = json.loads(files[0].read_text())
    assert saved["results"][0]["trace_id"] == "abc123"


def test_run_records_failed_query_and_reports_it(tmp_path):
    result = live_queries.run(make_args(tmp_path, limit=3), client=FakeClient([], status=404))
    assert result["errors"] == 3
    assert all(r["trace_id"] is None and "HTTP 404" in r["error"] for r in result["results"])
