"""Write reproducible CSV, JSON, Markdown, and methodology reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from benchmarks.harness_gain import PROTOCOL_VERSION
from benchmarks.harness_gain.schemas import RunRecord
from benchmarks.harness_gain.scoring import arm_statistics, harness_gains
from benchmarks.harness_gain.secret_redaction import write_json, write_text


def load_records(artifact_root: Path, phase: str | None = None) -> list[RunRecord]:
    records = []
    for path in artifact_root.glob("*/metadata.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if phase is None or data.get("phase") == phase:
            records.append(RunRecord.model_validate(data))
    return sorted(records, key=lambda item: (item.phase, item.run_id))


def write_reports(root: Path, records: list[RunRecord], *, phase: str = "main") -> dict[str, Any]:
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    selected = [
        record
        for record in records
        if record.phase == phase and record.protocol_version == PROTOCOL_VERSION
    ]
    stats = arm_statistics(selected)
    gains = harness_gains(stats)
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "phase": phase,
        "model": "deepseek-v4-flash",
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "sample_size": len(selected),
        "current_protocol_cost": sum(record.estimated_cost for record in selected),
        "global_cost": live_spend(root, records),
        "arms": stats,
        "harness_gains": gains,
        "runs": [record.model_dump(mode="json") for record in selected],
    }
    write_json(reports / "results.json", payload)
    _write_csv(reports / "results.csv", selected)
    write_text(reports / "summary.md", _summary(payload))
    write_text(reports / "failures.md", _failures(selected))
    write_text(reports / "methodology.md", _methodology(selected))
    return payload


def effective_cost(root: Path, record: RunRecord) -> float:
    if record.estimated_cost > 0 or record.arm_id.value != "mimocode":
        return record.estimated_cost
    session_path = root / "artifacts" / record.run_id / "session-export.json"
    if not session_path.exists():
        return 0.0
    from benchmarks.harness_gain.runners.mimocode_runner import _usage

    try:
        session = json.loads(session_path.read_text(encoding="utf-8"))
        recovered = _usage(session).estimated_cost
        if recovered > 0:
            return recovered
        from benchmarks.harness_gain.runners.mimocode_runner import usage_for_target

        return usage_for_target(root / "targets" / record.run_id).estimated_cost
    except (OSError, ValueError, TypeError):
        return 0.0


def live_spend(root: Path, records: list[RunRecord]) -> float:
    total = sum(effective_cost(root, record) for record in records)
    recorded_ids = {record.run_id for record in records}
    from benchmarks.harness_gain.runners.mimocode_runner import usage_for_target

    targets = root / "targets"
    if not targets.exists():
        return total
    for target in targets.iterdir():
        if (
            target.is_dir()
            and "-mimocode-r" in target.name
            and target.name not in recorded_ids
        ):
            total += usage_for_target(target).estimated_cost
    return total


def _write_csv(path: Path, records: list[RunRecord]) -> None:
    rows = [record.model_dump(mode="json") for record in records]
    fields = list(rows[0]) if rows else list(RunRecord.model_fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )


def _summary(payload: dict[str, Any]) -> str:
    lines = [
        "# DeepSeek harness-gain benchmark",
        "",
        (
            f"On benchmark protocol {payload['protocol_version']}, task set "
            "`taskforge_greenfield, ttl_cache_bugfix, csv_export_feature, config_refactor`, "
            f"model `deepseek-v4-flash`, budget 10 minutes / 3 calls / 12,288 output tokens / "
            f"$0.03 per run, sample size {payload['sample_size']}:"
        ),
        f"Global live cost including invalid pilots: `${payload['global_cost']:.6f}`.",
        "",
        "| Arm | Valid | Infra failures | Mean score | Exact pass | Hidden pass | Cost | Median s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, stats in payload["arms"].items():
        lines.append(
            f"| {arm} | {stats['valid_runs']} | {stats['infrastructure_failures']} | "
            f"{_fmt(stats['mean'])} | {_pct(stats['exact_pass_rate'])} | "
            f"{_pct(stats['hidden_pass_rate'])} | ${stats['cost']:.6f} | "
            f"{_fmt(stats['median_wall_time'])} |"
        )
    lines.extend(["", "Harness gains:", ""])
    for name, value in payload["harness_gains"].items():
        lines.append(f"- `{name}`: {_fmt(value)}")
    lines.extend(
        [
            "",
            "These results are protocol- and task-set-specific; they are not a universal ranking "
            "of Hephaestus or MiMo-Code.",
        ]
    )
    return "\n".join(lines) + "\n"


def _failures(records: list[RunRecord]) -> str:
    lines = ["# Failures", ""]
    failures = [record for record in records if not record.exact_pass]
    if not failures:
        return "# Failures\n\nNo failed runs.\n"
    for record in failures:
        lines.append(
            f"- `{record.run_id}`: `{record.failure_code or record.final_status}` — "
            f"{record.failure_detail or 'hidden checks did not all pass'}"
        )
    return "\n".join(lines) + "\n"


def _methodology(records: list[RunRecord]) -> str:
    return f"""# Methodology

Protocol: `{PROTOCOL_VERSION}`.

- Same DeepSeek provider endpoint and `deepseek-v4-flash` model in all arms.
- Fixed randomized seed `56062026`; fresh git target and session for every run.
- Identical prompt and fixture hash for a task across arms.
- Hidden validators execute outside participant targets on disposable copies.
- Deterministic scoring: functional 70, explicit requirements 20, scope/safety 10.
- Infrastructure failures are reported separately from coding-quality scores.
- No model output was manually repaired, continued, or edited.
- Global live cost represented here: `${sum(record.estimated_cost for record in records):.6f}`.

MiMo call/token limits are observed rather than pre-enforced; runs therefore carry a protocol
mismatch instead of a false claim of complete budget parity.
"""


def _fmt(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.2f}"


def _pct(value: Any) -> str:
    return "n/a" if value is None else f"{100 * float(value):.1f}%"
