"""Arm C: isolated MiMo-Code wrapper invocation."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from benchmarks.harness_gain.schemas import FailureCode, ProviderUsage, RunnerResult
from benchmarks.harness_gain.secret_redaction import redact_data
from hephaestus.models.catalog import DEEPSEEK_V4_FLASH_PRICING

WRAPPER = Path(r"C:\Users\Admin\Desktop\mimo-deepseek-setup\scripts\mimo-deepseek-run.ps1")
DATABASE = Path(r"C:\Users\Admin\Desktop\mimo-deepseek-setup\data\mimocode.db")


def build_command(prompt: str, target: Path) -> list[str]:
    return [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(WRAPPER),
        "-WorkingDirectory",
        str(target),
        "-Agent",
        "build",
        "-Format",
        "json",
        "-Prompt",
        prompt,
    ]


def isolated_environment(session_root: Path) -> dict[str, str]:
    session_root.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "WINDIR": os.environ.get("WINDIR", ""),
        "COMSPEC": os.environ.get("COMSPEC", ""),
        "PATHEXT": os.environ.get("PATHEXT", ""),
        "TEMP": str(session_root),
        "TMP": str(session_root),
        "HOME": str(session_root),
        "USERPROFILE": str(session_root),
        "PYTHONIOENCODING": "utf-8",
        "MIMOCODE_DISABLE_PROJECT_CONFIG": "true",
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "UV_OFFLINE": "1",
        "NPM_CONFIG_OFFLINE": "true",
        "CARGO_NET_OFFLINE": "true",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "protocol.https.allow",
        "GIT_CONFIG_VALUE_0": "never",
    }


def run(prompt: str, target: Path, session_root: Path) -> RunnerResult:
    before_sessions = _session_ids(target)
    try:
        process = _run_with_tree_timeout(
            build_command(prompt, target),
            cwd=target,
            env=isolated_environment(session_root),
            timeout=600,
        )
    except subprocess.TimeoutExpired as error:
        new_sessions = _session_ids(target) - before_sessions
        session = _export_session(new_sessions)
        session["fresh_session"] = bool(new_sessions)
        session["new_session_count"] = len(new_sessions)
        session["terminated_at_wall_limit"] = True
        usage = _usage(session)
        usage.protocol_mismatch.append("provider calls and token cap are observed, not pre-enforced")
        return RunnerResult(
            failure_code=FailureCode.PROCESS_TIMEOUT,
            failure_detail="MiMo exceeded 600 seconds.",
            stdout=error.stdout or "",
            stderr=error.stderr or "",
            usage=usage,
            session_export=session,
        )
    new_sessions = _session_ids(target) - before_sessions
    session = _export_session(new_sessions) or _parse_json_output(process.stdout)
    session["fresh_session"] = bool(new_sessions)
    session["new_session_count"] = len(new_sessions)
    session["environment_policy"] = {
        "package_managers_offline": True,
        "git_https_disabled": True,
        "project_config_disabled": True,
    }
    usage = _usage(session)
    usage.protocol_mismatch.append("provider calls and token cap are observed, not pre-enforced")
    code = None if process.returncode == 0 else FailureCode.TOOL_FAILURE
    return RunnerResult(
        declared_success=process.returncode == 0,
        failure_code=code,
        failure_detail="" if code is None else f"MiMo wrapper exit code {process.returncode}",
        usage=usage,
        stdout=process.stdout,
        stderr=process.stderr,
        session_export=session,
    )


def _run_with_tree_timeout(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        if os.name == "nt":
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        else:
            process.kill()
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            error.cmd,
            timeout,
            output=stdout,
            stderr=stderr,
        ) from error
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _parse_json_output(text: str) -> dict[str, Any]:
    stripped = text.strip()
    candidates = [stripped, *reversed([line for line in stripped.splitlines() if line.strip()])]
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        return {"events": parsed}
    return {"raw_output_sha256_only": True}


def _usage(session: dict[str, Any]) -> ProviderUsage:
    messages = session.get("messages")
    if isinstance(messages, list):
        call_tokens: list[dict[str, Any]] = []
        for message in messages:
            data = message.get("data") if isinstance(message, dict) else None
            tokens = data.get("tokens") if isinstance(data, dict) else None
            if (
                isinstance(data, dict)
                and isinstance(tokens, dict)
                and int(tokens.get("total", 0) or 0) > 0
                and data.get("providerID") == "deepseek-bench"
                and data.get("modelID") == "deepseek-v4-flash"
            ):
                call_tokens.append(tokens)
        if call_tokens:
            uncached_input = sum(int(item.get("input", 0) or 0) for item in call_tokens)
            cached = sum(_cache_token(item, "read") for item in call_tokens)
            cache_write = sum(_cache_token(item, "write") for item in call_tokens)
            output = sum(
                int(item.get("output", 0) or 0) + int(item.get("reasoning", 0) or 0)
                for item in call_tokens
            )
            input_total = uncached_input + cached + cache_write
            pricing = DEEPSEEK_V4_FLASH_PRICING
            cost = (
                (uncached_input + cache_write) * pricing.input_cost_per_million
                + cached * (pricing.cached_input_cost_per_million or pricing.input_cost_per_million)
                + output * pricing.output_cost_per_million
            ) / 1_000_000
            return ProviderUsage(
                logical_provider_calls=len(call_tokens),
                transport_attempts=len(call_tokens),
                input_tokens=input_total,
                cached_tokens=cached,
                output_tokens=output,
                estimated_cost=cost,
            )
    totals = {
        "input_tokens": 0,
        "cached_tokens": 0,
        "output_tokens": 0,
        "estimated_cost": 0.0,
        "logical_provider_calls": 0,
        "transport_attempts": 0,
    }

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            lowered = {str(key).lower(): item for key, item in value.items()}
            for key, aliases in {
                "input_tokens": ("input_tokens", "prompt_tokens"),
                "cached_tokens": ("cached_tokens", "cached_input_tokens"),
                "output_tokens": ("output_tokens", "completion_tokens"),
                "estimated_cost": ("estimated_cost", "cost"),
            }.items():
                for alias in aliases:
                    item = lowered.get(alias)
                    if isinstance(item, (int, float)):
                        totals[key] = max(totals[key], item)
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(session)
    fallback_calls = _count_keys(session, {"model", "provider_response", "assistant"})
    totals["logical_provider_calls"] = max(1, fallback_calls) if session else 0
    totals["transport_attempts"] = totals["logical_provider_calls"]
    return ProviderUsage(**totals)


def _cache_token(tokens: dict[str, Any], kind: str) -> int:
    cache = tokens.get("cache")
    return int(cache.get(kind, 0) or 0) if isinstance(cache, dict) else 0


def _count_keys(value: Any, keys: set[str]) -> int:
    if isinstance(value, dict):
        own = int(any(str(key).lower() in keys for key in value))
        return own + sum(_count_keys(item, keys) for item in value.values())
    if isinstance(value, list):
        return sum(_count_keys(item, keys) for item in value)
    return 0


def _session_ids(target: Path) -> set[str]:
    if not DATABASE.exists():
        return set()
    try:
        with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True, timeout=5) as connection:
            rows = connection.execute(
                "SELECT id FROM session WHERE lower(directory) = lower(?)",
                (str(target.resolve()),),
            ).fetchall()
    except sqlite3.Error:
        return set()
    return {str(row[0]) for row in rows}


def _export_session(session_ids: set[str]) -> dict[str, Any]:
    if not session_ids or not DATABASE.exists():
        return {}
    placeholders = ",".join("?" for _ in session_ids)
    parameters = tuple(sorted(session_ids))
    try:
        with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True, timeout=5) as connection:
            sessions = connection.execute(
                f"""
                SELECT id, parent_id, directory, title, version, summary_additions,
                       summary_deletions, summary_files, time_created, time_updated
                FROM session WHERE id IN ({placeholders})
                ORDER BY time_created
                """,
                parameters,
            ).fetchall()
            messages = connection.execute(
                f"""
                SELECT id, session_id, agent_id, time_created, time_updated, data
                FROM message WHERE session_id IN ({placeholders}) ORDER BY time_created
                """,
                parameters,
            ).fetchall()
            parts = connection.execute(
                f"""
                SELECT id, session_id, message_id, time_created, time_updated, data
                FROM part WHERE session_id IN ({placeholders}) ORDER BY time_created
                """,
                parameters,
            ).fetchall()
    except sqlite3.Error:
        return {}
    if not sessions:
        return {}
    session_rows = [
        {
            "id": row[0],
            "parent_id": row[1],
            "directory": row[2],
            "title": row[3],
            "version": row[4],
            "summary_additions": row[5],
            "summary_deletions": row[6],
            "summary_files": row[7],
            "time_created": row[8],
            "time_updated": row[9],
        }
        for row in sessions
    ]
    primary = next(
        (
            session
            for session in session_rows
            if session["parent_id"] not in session_ids
        ),
        session_rows[0],
    )
    payload = {
        "session": primary,
        "sessions": session_rows,
        "messages": [
            {
                "id": row[0],
                "session_id": row[1],
                "agent_id": row[2],
                "time_created": row[3],
                "time_updated": row[4],
                "data": _safe_json(row[5]),
            }
            for row in messages
        ],
        "parts": [
            {
                "id": row[0],
                "session_id": row[1],
                "message_id": row[2],
                "time_created": row[3],
                "time_updated": row[4],
                "data": _safe_json(row[5]),
            }
            for row in parts
        ],
    }
    redacted = redact_data(payload)
    return redacted if isinstance(redacted, dict) else {}


def _safe_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def usage_for_target(target: Path) -> ProviderUsage:
    return _usage(_export_session(_session_ids(target)))
