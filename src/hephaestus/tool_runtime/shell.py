"""Safe shell command wrapper for the tool runtime."""

from __future__ import annotations

import subprocess
import time

from hephaestus.tool_runtime.filesystem import resolve_workspace
from hephaestus.tool_runtime.schemas import (
    ShellCommandRequest,
    ShellCommandResult,
    ToolExecutionStatus,
)


def run_shell_command(request: ShellCommandRequest) -> ShellCommandResult:
    """Execute a shell command with timeout and output truncation."""

    cwd = resolve_workspace(request.cwd)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            request.command,
            cwd=str(cwd),
            shell=True,
            text=True,
            capture_output=True,
            timeout=request.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        duration = time.monotonic() - started
        stdout, stdout_truncated = _truncate(_to_text(error.stdout), request.max_output_chars)
        stderr, stderr_truncated = _truncate(_to_text(error.stderr), request.max_output_chars)
        return ShellCommandResult(
            command=request.command,
            cwd=str(cwd),
            status=ToolExecutionStatus.TIMED_OUT,
            stdout=stdout,
            stderr=stderr,
            exit_code=None,
            duration_seconds=duration,
            timed_out=True,
            output_truncated=stdout_truncated or stderr_truncated,
        )
    duration = time.monotonic() - started
    stdout, stdout_truncated = _truncate(completed.stdout, request.max_output_chars)
    stderr, stderr_truncated = _truncate(completed.stderr, request.max_output_chars)
    status = ToolExecutionStatus.SUCCEEDED if completed.returncode == 0 else ToolExecutionStatus.FAILED
    return ShellCommandResult(
        command=request.command,
        cwd=str(cwd),
        status=status,
        stdout=stdout,
        stderr=stderr,
        exit_code=completed.returncode,
        duration_seconds=duration,
        timed_out=False,
        output_truncated=stdout_truncated or stderr_truncated,
    )


def _truncate(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[:limit] + "\n...[truncated]", True


def _to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return str(value)
