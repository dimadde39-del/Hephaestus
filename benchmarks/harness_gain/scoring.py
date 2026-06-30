"""Deterministic scoring and aggregate benchmark metrics."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

from benchmarks.harness_gain.schemas import RunRecord, ValidationResult


def score_validation(result: ValidationResult) -> tuple[float, float, float, float]:
    scores: defaultdict[str, float] = defaultdict(float)
    for check in result.checks:
        if check.passed:
            scores[check.category] += check.weight
    functional = min(70.0, scores["functional"])
    requirements = min(20.0, scores["requirements"])
    safety = min(10.0, scores["safety"])
    return functional, requirements, safety, functional + requirements + safety


def arm_statistics(records: list[RunRecord]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for arm in sorted({record.arm_id.value for record in records}):
        rows = [record for record in records if record.arm_id.value == arm]
        valid = [record for record in rows if not record.infrastructure_failure]
        scores = [record.verifier_adjusted_score for record in valid]
        exact = sum(record.exact_pass for record in valid)
        repaired = [record for record in valid if record.repair_calls > 0]
        hidden_rates = [record.hidden_check_pass_rate for record in valid]
        output[arm] = {
            "runs": len(rows),
            "valid_runs": len(valid),
            "infrastructure_failures": len(rows) - len(valid),
            "mean": statistics.mean(scores) if scores else None,
            "median": statistics.median(scores) if scores else None,
            "min": min(scores) if scores else None,
            "max": max(scores) if scores else None,
            "standard_deviation": statistics.stdev(scores) if len(scores) > 1 else None,
            "exact_pass_rate": exact / len(valid) if valid else None,
            "hidden_pass_rate": statistics.mean(hidden_rates) if hidden_rates else None,
            "exact_pass_confidence_interval": wilson_interval(exact, len(valid)),
            "false_success_rate": (
                sum(record.false_success for record in valid) / len(valid) if valid else None
            ),
            "scope_violation_rate": (
                sum(record.scope_violations > 0 for record in valid) / len(valid) if valid else None
            ),
            "infrastructure_failure_rate": (len(rows) - len(valid)) / len(rows) if rows else None,
            "repair_success_rate": (
                sum(record.exact_pass for record in repaired) / len(repaired) if repaired else None
            ),
            "median_wall_time": (
                statistics.median(record.wall_time for record in valid) if valid else None
            ),
            "tokens": sum(record.input_tokens + record.output_tokens for record in rows),
            "cost": sum(record.estimated_cost for record in rows),
            "calls": sum(record.logical_provider_calls for record in rows),
            "repair_calls": sum(record.repair_calls for record in rows),
            "cost_per_exact_pass": (
                sum(record.estimated_cost for record in valid) / exact if exact else None
            ),
            "tokens_per_exact_pass": (
                sum(record.input_tokens + record.output_tokens for record in valid) / exact
                if exact
                else None
            ),
        }
    return output


def wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2))
    return [max(0.0, center - margin / denominator), min(1.0, center + margin / denominator)]


def harness_gains(stats: dict[str, Any]) -> dict[str, float | None]:
    def mean(arm: str) -> float | None:
        item = stats.get(arm, {}).get("mean")
        return float(item) if item is not None else None

    heph = mean("hephaestus")
    one = mean("bare_one_shot")
    two = mean("bare_two_stage")
    mimo = mean("mimocode")

    def delta(left: float | None, right: float | None) -> float | None:
        return left - right if left is not None and right is not None else None

    return {
        "HG_one_shot": delta(heph, one),
        "HG_two_stage": delta(heph, two),
        "MiMo_gain": delta(mimo, two),
        "Competitive_gap": delta(heph, mimo),
    }
