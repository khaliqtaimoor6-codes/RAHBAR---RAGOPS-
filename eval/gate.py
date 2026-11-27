#!/usr/bin/env python3
"""Part C2 / F2: the release gate.

Compares a candidate suite result against the Part B baseline across all three levels
(module, component, end-to-end). Thresholds come from a YAML file: `eval/gate-thresholds.yaml`
locally, the `rahbar-gate` ConfigMap on the cluster. One PASS/FAIL line is printed per rule
and the process exits 1 when any rule (or a compatibility check) fails. CI and the eval Job
use that exit code; nothing is retried.

    python eval/gate.py --candidate eval/results/suite/ragops-cand.json \
        --baseline eval/results/suite/ragops-20261126T104001Z-rejudged-1.json \
        --config eval/gate-thresholds.yaml

Environment equivalents (used by ragops_suite.py and the Kubernetes Job):
    GATE_CANDIDATE, GATE_BASELINE, GATE_CONFIG, GATE_OUT

Exit codes: 0 pass, 1 gate failed, 2 bad input (missing file, invalid config).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_BASELINE = HERE / "results/suite/ragops-20261126T104001Z-rejudged-1.json"
DEFAULT_CONFIG = HERE / "gate-thresholds.yaml"

# Where a metric lives inside one `runs[i]` of a ragops_suite result.
LEVEL_PATHS = {
    "module": ("module",),
    "component": ("component", "clean"),
    "component_typos": ("component", "typos"),
    "end_to_end": ("end_to_end",),
}
TOL = 1e-9


def aggregate(result: dict[str, Any], level: str, variant: str, metric: str) -> float | None:
    """Mean of a metric across the result's runs; None when no run measured it.

    The baseline has two seeded runs, a candidate usually one. Averaging keeps the
    comparison fair and lets a candidate that was not re-run twice still be gated.
    """
    key = level if variant == "clean" else f"{level}_typos"
    path = LEVEL_PATHS.get(key)
    if path is None:
        return None
    values: list[float] = []
    for run in result.get("runs", []):
        node: Any = run
        try:
            for part in path:
                node = node[part]
            value = node.get(metric)
        except (KeyError, TypeError):
            value = None
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            values.append(float(value))
    return round(sum(values) / len(values), 4) if values else None


def question_ids(result: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for run in result.get("runs", []):
        for answer in run.get("answers", []):
            if answer.get("id") is not None:
                ids.add(str(answer["id"]))
    return ids


def compatibility_failures(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    """A regression number is meaningless unless both runs tested the same thing."""
    failures: list[str] = []
    bg, cg = baseline.get("golden") or {}, candidate.get("golden") or {}
    if bg.get("questions") != cg.get("questions"):
        failures.append(
            f"golden sets differ: baseline {bg.get('questions')} questions, "
            f"candidate {cg.get('questions')} questions"
        )
    b_ids, c_ids = question_ids(baseline), question_ids(candidate)
    if b_ids != c_ids:
        failures.append(
            "golden question ids differ: "
            f"missing in candidate {sorted(b_ids - c_ids)[:6]}, "
            f"extra in candidate {sorted(c_ids - b_ids)[:6]}"
        )
    if baseline.get("embed_model") != candidate.get("embed_model"):
        failures.append(
            f"embedding model changed: baseline {baseline.get('embed_model')!r}, "
            f"candidate {candidate.get('embed_model')!r}; compare inside one pin only"
        )
    b_ver, c_ver = baseline.get("embedding_version"), candidate.get("embedding_version")
    if not b_ver or not c_ver:
        failures.append("embedding version missing from a result (traces not mounted?)")
    elif b_ver != c_ver:
        failures.append(f"embedding version changed: {b_ver!r} -> {c_ver!r}")
    if not candidate.get("collection"):
        failures.append("candidate collection not recorded (no trace to identify what was tested)")
    return failures


def rule_requirement(rule: dict[str, Any], floor: float | None) -> str:
    parts: list[str] = []
    if "min" in rule:
        parts.append(f">= {rule['min']}")
    if "max" in rule:
        parts.append(f"<= {rule['max']}")
    if "max_drop" in rule:
        parts.append(f">= {floor:.4f} (baseline - {rule['max_drop']})")
    if "max_rise" in rule:
        parts.append(f"<= {floor:.4f} (baseline + {rule['max_rise']})")
    if "max_rise_pct" in rule:
        parts.append(f"<= {floor:.4f} (baseline x {1 + rule['max_rise_pct'] / 100:.2f})")
    return " and ".join(parts) or "measured"


@dataclass
class GateResult:
    candidate: Path
    baseline: Path
    config: Path
    candidate_meta: dict[str, Any]
    baseline_meta: dict[str, Any]
    checks: list[dict[str, Any]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": "pass" if self.passed else "fail",
            "candidate": str(self.candidate),
            "baseline": str(self.baseline),
            "config": str(self.config),
            "candidate_meta": self.candidate_meta,
            "baseline_meta": self.baseline_meta,
            "checks": self.checks,
            "failures": self.failures,
            "generated_at": self.generated_at,
        }

    def markdown(self) -> str:
        lines = [
            f"# RAHBAR release gate: {'PASS' if self.passed else 'FAIL'}",
            "",
            f"- candidate: `{self.candidate}` — collection "
            f"{(self.candidate_meta.get('collection') or {}).get('name')} "
            f"({(self.candidate_meta.get('collection') or {}).get('chunks')} chunks)",
            f"- baseline: `{self.baseline}` — collection "
            f"{(self.baseline_meta.get('collection') or {}).get('name')} "
            f"({(self.baseline_meta.get('collection') or {}).get('chunks')} chunks)",
            f"- config: `{self.config}`",
            f"- generated: {self.generated_at}",
            "",
            "| rule | level | metric | baseline | candidate | delta | requirement | result |",
            "|---|---|---|---:|---:|---:|---|---|",
        ]
        for c in self.checks:
            baseline = "—" if c["baseline"] is None else f"{c['baseline']:.4f}"
            candidate = "—" if c["candidate"] is None else f"{c['candidate']:.4f}"
            delta = "—" if c["delta"] is None else f"{c['delta']:+.4f}"
            result = "PASS" if c["passed"] else "**FAIL**"
            lines.append(
                f"| {c['id']} | {c['level']} | {c['metric']} | {baseline} | {candidate} | "
                f"{delta} | {c['requirement']} | {result} |"
            )
        lines += ["", "## Failures", ""]
        lines += [f"- {f}" for f in self.failures] if self.failures else ["- none"]
        return "\n".join(lines) + "\n"

    def write(self, out: Path) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".json").write_text(
            json.dumps(self.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        out.with_suffix(".md").write_text(self.markdown(), encoding="utf-8")


def check_rule(
    rule: dict[str, Any], baseline: float | None, candidate: float | None
) -> dict[str, Any]:
    level, variant, metric = rule["level"], rule.get("variant", "clean"), rule["metric"]
    check: dict[str, Any] = {
        "id": rule["id"], "level": level, "metric": f"{variant}.{metric}" if variant != "clean" else metric,
        "baseline": baseline, "candidate": candidate,
        "delta": None if baseline is None or candidate is None else round(candidate - baseline, 4),
        "requirement": "", "passed": True, "message": "",
    }
    floor: float | None = None
    if "max_drop" in rule or "max_rise" in rule or "max_rise_pct" in rule:
        floor = baseline
    check["requirement"] = rule_requirement(rule, floor)

    messages: list[str] = []
    if candidate is None:
        if rule.get("required", True):
            messages.append("metric not measured in the candidate")
    else:
        if "min" in rule and candidate < float(rule["min"]) - TOL:
            messages.append(f"{candidate:.4f} < minimum {rule['min']}")
        if "max" in rule and candidate > float(rule["max"]) + TOL:
            messages.append(f"{candidate:.4f} > maximum {rule['max']}")
        if "max_drop" in rule:
            if baseline is None:
                messages.append("baseline metric not measured")
            elif candidate < baseline - float(rule["max_drop"]) - TOL:
                messages.append(f"drop {baseline - candidate:.4f} > allowed {rule['max_drop']}")
        if "max_rise" in rule:
            if baseline is None:
                messages.append("baseline metric not measured")
            elif candidate > baseline + float(rule["max_rise"]) + TOL:
                messages.append(f"rise {candidate - baseline:.4f} > allowed {rule['max_rise']}")
        if "max_rise_pct" in rule:
            if baseline is None:
                messages.append("baseline metric not measured")
            else:
                limit = baseline * (1 + float(rule["max_rise_pct"]) / 100)
                if candidate > limit + TOL:
                    messages.append(f"rise to {candidate:.4f} > allowed {limit:.4f}")
    check["passed"] = not messages
    check["message"] = "; ".join(messages)
    return check


def evaluate(
    candidate_path: Path, baseline_path: Path, config_path: Path, out: Path | None = None
) -> GateResult:
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if config.get("version") != 1:
        raise ValueError(f"unsupported gate config version: {config.get('version')!r}")
    rules = config.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("gate config has no rules")

    result = GateResult(candidate_path, baseline_path, config_path,
                        {k: candidate.get(k) for k in ("collection", "embedding_version", "golden")},
                        {k: baseline.get(k) for k in ("collection", "embedding_version", "golden")})
    result.failures.extend(f"compatibility: {m}" for m in compatibility_failures(baseline, candidate))
    for rule in rules:
        for key in ("id", "level", "metric"):
            if key not in rule:
                raise ValueError(f"gate rule missing {key!r}: {rule}")
        baseline_value = aggregate(baseline, rule["level"], rule.get("variant", "clean"), rule["metric"])
        candidate_value = aggregate(candidate, rule["level"], rule.get("variant", "clean"), rule["metric"])
        check = check_rule(rule, baseline_value, candidate_value)
        result.checks.append(check)
        if not check["passed"]:
            result.failures.append(f"{check['id']}: {check['message']}")
    if out is not None:
        result.write(out)
    return result


def main(argv: list[str] | None = None) -> int:
    env = os.environ.get
    ap = argparse.ArgumentParser(description="RAHBAR release gate (Part C2 / F2).")
    ap.add_argument("--candidate", default=env("GATE_CANDIDATE", ""), help="suite result JSON to gate")
    ap.add_argument("--baseline", default=env("GATE_BASELINE", str(DEFAULT_BASELINE)))
    ap.add_argument("--config", default=env("GATE_CONFIG", str(DEFAULT_CONFIG)))
    ap.add_argument("--out", default=env("GATE_OUT", ""),
                    help="write <out>.json/.md (a path prefix, extension added)")
    args = ap.parse_args(argv)
    if not args.candidate:
        ap.error("--candidate is required (or set GATE_CANDIDATE)")
    try:
        out = Path(args.out) if args.out else None
        result = evaluate(Path(args.candidate), Path(args.baseline), Path(args.config), out)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"gate input error: {exc}", file=sys.stderr)
        return 2
    print(result.markdown())
    print(f"GATE {'PASSED' if result.passed else 'FAILED'} "
          f"({len(result.checks) - sum(not c['passed'] for c in result.checks)}/{len(result.checks)} rules)")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
