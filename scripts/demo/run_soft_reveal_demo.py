from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

COMMANDS = [
    "uv run heph doctor",
    "uv run heph repo inspect .",
    "uv run heph release plan . --pareto --qubo --evaluate",
    "uv run heph release list",
    "uv run heph runs",
    "uv run heph explain <optimizer_run_id> --summary",
    "uv run heph pareto show <frontier_id>",
    "uv run heph qubo show <problem_id>",
    "uv run heph learn signals --run <optimizer_run_id>",
]


def print_commands() -> None:
    print("Soft reveal demo command sequence:")
    print()
    for command in COMMANDS:
        print(command)
    print()
    print("Run with --run to execute the main flow and print parsed follow-up IDs.")


def run_command(args: list[str]) -> str:
    print()
    print(f"$ {' '.join(args)}")
    completed = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(completed.stdout)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed.stdout


def first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    if match is None:
        return None
    return match.group(1)


def run_demo() -> None:
    run_command(["uv", "run", "heph", "doctor"])
    run_command(["uv", "run", "heph", "repo", "inspect", "."])
    release_output = run_command(
        ["uv", "run", "heph", "release", "plan", ".", "--pareto", "--qubo", "--evaluate"]
    )

    release_id = first_match(r"Release plan:\s*(release_[a-f0-9]+)", release_output)
    optimizer_run_id = first_match(r"Optimizer run:\s*(run_[a-f0-9]+)", release_output)
    frontier_id = first_match(r"(frontier_[a-f0-9]+)", release_output)
    problem_id = first_match(r"(qubo_[a-f0-9]+)", release_output)

    run_command(["uv", "run", "heph", "release", "list"])
    run_command(["uv", "run", "heph", "runs"])

    print()
    print("Parsed follow-up IDs:")
    print(f"release_run_id={release_id or '<not found>'}")
    print(f"optimizer_run_id={optimizer_run_id or '<not found>'}")
    print(f"frontier_id={frontier_id or '<not found>'}")
    print(f"problem_id={problem_id or '<not found>'}")

    if optimizer_run_id:
        run_command(["uv", "run", "heph", "explain", optimizer_run_id, "--summary"])
        run_command(["uv", "run", "heph", "learn", "signals", "--run", optimizer_run_id])
    if frontier_id:
        run_command(["uv", "run", "heph", "pareto", "show", frontier_id])
    if problem_id:
        run_command(["uv", "run", "heph", "qubo", "show", problem_id])


def main() -> int:
    parser = argparse.ArgumentParser(description="Print or run the Hephaestus soft reveal demo.")
    parser.add_argument("--run", action="store_true", help="Execute the demo commands.")
    args = parser.parse_args()

    if args.run:
        run_demo()
    else:
        print_commands()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
