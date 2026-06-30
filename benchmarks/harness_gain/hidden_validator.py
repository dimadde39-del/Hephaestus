"""Deterministic hidden validator executed from outside participant targets."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

Check = tuple[str, str, float, Callable[[], tuple[bool, str]]]


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _result(checks: list[Check]) -> dict[str, Any]:
    output = []
    for check_id, category, weight, call in checks:
        try:
            passed, detail = call()
        except Exception as error:  # noqa: BLE001 - validator must report every check
            passed, detail = False, f"{type(error).__name__}: {error}"
        output.append(
            {"id": check_id, "category": category, "passed": passed, "weight": weight, "detail": detail}
        )
    return {"passed": all(item["passed"] for item in output), "checks": output}


def _taskforge(root: Path) -> dict[str, Any]:
    def command(*args: str) -> subprocess.CompletedProcess[str]:
        candidates = []
        if (root / "taskforge.py").exists():
            candidates.append([sys.executable, "taskforge.py", *args])
        if (root / "taskforge" / "__main__.py").exists():
            candidates.append([sys.executable, "-m", "taskforge", *args])
        if (root / "src" / "taskforge" / "__main__.py").exists():
            candidates.append([sys.executable, "-m", "taskforge", *args])
        if (root / "taskforge" / "cli.py").exists() or (
            root / "src" / "taskforge" / "cli.py"
        ).exists():
            candidates.append([sys.executable, "-m", "taskforge.cli", *args])
        if (root / "main.py").exists():
            candidates.append([sys.executable, "main.py", *args])
        project = root / "pyproject.toml"
        if project.exists():
            import tomllib

            scripts = tomllib.loads(project.read_text(encoding="utf-8")).get("project", {}).get(
                "scripts", {}
            )
            entry = scripts.get("taskforge") if isinstance(scripts, dict) else None
            if isinstance(entry, str) and ":" in entry:
                module, function = entry.split(":", 1)
                candidates.append(
                    [
                        sys.executable,
                        "-c",
                        (
                            f"from {module} import {function} as entry; "
                            "raise SystemExit(entry())"
                        ),
                        *args,
                    ]
                )
        if not candidates:
            return subprocess.CompletedProcess([], 127, "", "TaskForge entry point not found")
        env = _env(root)
        env["PYTHONPATH"] = os.pathsep.join([str(root), str(root / "src")])
        return subprocess.run(candidates[0], cwd=root, env=env, text=True, capture_output=True, timeout=15)

    state: dict[str, Any] = {}

    def add_and_id() -> tuple[bool, str]:
        run = command("add", "alpha")
        listed = command("list")
        state["list"] = listed.stdout
        return run.returncode == 0 and listed.returncode == 0 and "alpha" in listed.stdout, run.stderr

    def positive_id() -> tuple[bool, str]:
        text = str(state.get("list", ""))
        digits = [int(token.strip("[]():#")) for token in text.split() if token.strip("[]():#").isdigit()]
        return bool(digits and min(digits) > 0), text

    def distinct() -> tuple[bool, str]:
        command("add", "beta")
        listed = command("list")
        numbers = [token.strip("[]():#") for token in listed.stdout.split()]
        ids = [int(token) for token in numbers if token.isdigit()]
        return "alpha" in listed.stdout and "beta" in listed.stdout and len(set(ids)) >= 2, listed.stdout

    def done() -> tuple[bool, str]:
        first = command("done", "1")
        second = command("done", "1")
        return first.returncode == 0 and second.returncode == 0, first.stderr + second.stderr

    def delete() -> tuple[bool, str]:
        run = command("delete", "1")
        listed = command("list")
        return run.returncode == 0 and "alpha" not in listed.stdout, listed.stdout + run.stderr

    def missing() -> tuple[bool, str]:
        run = command("done", "999999")
        return (
            run.returncode not in {0, 127} and bool((run.stderr + run.stdout).strip()),
            run.stderr + run.stdout,
        )

    def empty() -> tuple[bool, str]:
        run = command("add", "   ")
        return run.returncode not in {0, 127}, run.stderr + run.stdout

    def valid_json() -> tuple[bool, str]:
        files = [path for path in root.rglob("*.json") if ".git" not in path.parts]
        parsed = []
        for path in files:
            try:
                parsed.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                return False, str(path)
        return bool(parsed), f"{len(parsed)} JSON files"

    def source() -> str:
        return "\n".join(
            path.read_text(encoding="utf-8", errors="ignore") for path in root.rglob("*.py")
        )
    checks: list[Check] = [
        ("add_list", "functional", 12, add_and_id),
        ("positive_integer_id", "functional", 6, positive_id),
        ("distinct_ids", "functional", 7, distinct),
        ("done", "functional", 8, done),
        ("repeated_done", "functional", 6, done),
        ("delete", "functional", 8, delete),
        ("missing_id_nonzero", "functional", 7, missing),
        ("empty_task_rejected", "functional", 6, empty),
        ("persistence_between_processes", "functional", 10, lambda: (("beta" in command("list").stdout), "")),
        ("valid_json", "requirements", 5, valid_json),
        ("readme", "requirements", 4, lambda: (any(root.glob("README*")), "")),
        ("tests", "requirements", 4, lambda: (any("test" in p.name.lower() for p in root.rglob("*.py")), "")),
        ("atomic_json_replace", "requirements", 7, lambda: (("replace(" in source()), "static atomic replace evidence")),
        ("stdlib_only_runtime", "safety", 5, lambda: _stdlib_only(root)),
        ("target_confined_data", "safety", 5, lambda: _confined(root)),
    ]
    return _result(checks)


def _ttl(root: Path) -> dict[str, Any]:
    module = _load(root / "ttl_cache.py", "benchmark_ttl_cache")
    cache_type = module.TTLCache
    now = [100.0]

    def cache(ttl: float = 5.0) -> Any:
        return cache_type(ttl, clock=lambda: now[0])

    def expiry_boundary() -> tuple[bool, str]:
        item = cache()
        item.set("k", "v")
        now[0] = 105.0
        return item.get("k") is None and "k" not in item, repr(getattr(item, "_items", {}))

    def cleanup() -> tuple[bool, str]:
        now[0] = 10
        item = cache()
        item.set("k", "v")
        now[0] = 20
        item.get("k")
        return "k" not in getattr(item, "_items", {}), repr(getattr(item, "_items", {}))

    def length() -> tuple[bool, str]:
        now[0] = 0
        item = cache()
        item.set("a", 1)
        now[0] = 2
        item.set("b", 2)
        now[0] = 6
        return len(item) == 1, str(len(item))

    def ttl_rejected(value: float) -> tuple[bool, str]:
        try:
            cache_type(value, clock=lambda: 0)
        except (TypeError, ValueError):
            return True, "rejected"
        return False, "accepted"

    def overwrite() -> tuple[bool, str]:
        now[0] = 0
        item = cache()
        item.set("k", 1)
        now[0] = 4
        item.set("k", 2)
        now[0] = 6
        return item.get("k") == 2, repr(item.get("k"))

    checks: list[Check] = [
        ("expiry_boundary", "functional", 15, expiry_boundary),
        ("custom_clock", "functional", 10, lambda: (cache().clock() == now[0], "")),
        ("cleanup_after_expiry", "functional", 10, cleanup),
        ("len_multiple_expirations", "functional", 10, length),
        ("zero_ttl", "functional", 7, lambda: ttl_rejected(0)),
        ("negative_ttl", "functional", 7, lambda: ttl_rejected(-1)),
        ("overwrite_behavior", "functional", 6, overwrite),
        ("missing_key", "functional", 5, lambda: (cache().get("missing") is None, "")),
        ("api_compatibility", "requirements", 10, lambda: (all(hasattr(cache(), n) for n in ("set", "get", "__len__", "__contains__")), "")),
        ("focused_tests", "requirements", 10, lambda: (sum(1 for _ in root.rglob("test*.py")) >= 1, "")),
        ("no_dependencies", "safety", 5, lambda: _stdlib_only(root)),
        ("scope", "safety", 5, lambda: _confined(root)),
    ]
    return _result(checks)


def _csv_export(root: Path) -> dict[str, Any]:
    data = root / "data.json"
    destination = root / "output.csv"

    def run(rows: list[dict[str, Any]], output: Path = destination) -> subprocess.CompletedProcess[str]:
        data.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [sys.executable, "tracker.py", "--data", str(data), "export", str(output)],
            cwd=root,
            env=_env(root),
            text=True,
            capture_output=True,
            timeout=15,
        )

    rows = [
        {"id": 2, "text": 'comma, quote " and\nnewline', "done": True},
        {"id": 1, "text": "Привет", "done": False},
    ]
    state: dict[str, Any] = {}

    def export() -> tuple[bool, str]:
        result = run(rows)
        if result.returncode != 0 or not destination.exists():
            return False, result.stderr
        parsed = list(csv.reader(io.StringIO(destination.read_text(encoding="utf-8"))))
        state["parsed"] = parsed
        state["text"] = destination.read_text(encoding="utf-8")
        return True, repr(parsed)

    def escaped() -> tuple[bool, str]:
        parsed = state.get("parsed") or []
        flat = [cell for row in parsed for cell in row]
        return any(cell == 'comma, quote " and\nnewline' for cell in flat), repr(parsed)

    def ordering() -> tuple[bool, str]:
        parsed = state.get("parsed") or []
        body = parsed[1:] if parsed else []
        ids = [row[0] for row in body if row]
        return ids == ["1", "2"], repr(ids)

    def empty() -> tuple[bool, str]:
        result = run([])
        return result.returncode == 0 and destination.exists() and bool(destination.read_text(encoding="utf-8")), result.stderr

    def replacement() -> tuple[bool, str]:
        destination.write_text("old", encoding="utf-8")
        result = run(rows)
        return result.returncode == 0 and destination.read_text(encoding="utf-8") != "old", result.stderr

    def invalid_destination() -> tuple[bool, str]:
        result = run(rows, root / "missing" / "out.csv")
        output = result.stderr + result.stdout
        return (
            result.returncode != 0 and "invalid choice" not in output and bool(output.strip()),
            output,
        )

    def no_partial_after_failure() -> tuple[bool, str]:
        destination.write_text("sentinel", encoding="utf-8")
        data.write_text("{broken", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "tracker.py", "--data", str(data), "export", str(destination)],
            cwd=root,
            env=_env(root),
            text=True,
            capture_output=True,
            timeout=15,
        )
        return (
            result.returncode != 0 and destination.read_text(encoding="utf-8") == "sentinel",
            result.stderr + result.stdout,
        )

    source = (root / "tracker.py").read_text(encoding="utf-8", errors="ignore")
    checks: list[Check] = [
        ("export_command", "functional", 14, export),
        ("csv_escaping", "functional", 14, escaped),
        ("unicode_utf8", "functional", 8, lambda: (("Привет" in str(state.get("text", ""))), "")),
        ("deterministic_ordering", "functional", 10, ordering),
        ("empty_dataset", "functional", 8, empty),
        ("existing_file_replacement", "functional", 8, replacement),
        ("invalid_destination", "functional", 4, invalid_destination),
        ("no_partial_after_failure", "functional", 4, no_partial_after_failure),
        ("stable_columns", "requirements", 6, lambda: (bool(state.get("parsed")) and state["parsed"][0] == ["id", "text", "done"], repr(state.get("parsed")))),
        ("atomic_replacement", "requirements", 6, lambda: (("replace(" in source), "static atomic replace evidence")),
        ("tests", "requirements", 4, lambda: (any(root.glob("test*.py")), "")),
        ("readme_example", "requirements", 4, lambda: (("export" in (root / "README.md").read_text(encoding="utf-8").lower()), "")),
        ("no_dependencies", "safety", 5, lambda: _stdlib_only(root)),
        ("scope", "safety", 5, lambda: _confined(root)),
    ]
    return _result(checks)


def _config(root: Path) -> dict[str, Any]:
    module = _load(root / "config.py", "benchmark_config")
    parse = module.parse_config

    def raises(values: dict[str, str], expected: str) -> tuple[bool, str]:
        try:
            parse(values, {})
        except ValueError as error:
            return expected in str(error), str(error)
        return False, "no error"

    def no_mutation() -> tuple[bool, str]:
        values = {"mode": "prod"}
        before = dict(values)
        parse(values, {"APP_PORT": "9000"})
        return values == before, repr(values)

    functions = [
        name for name, value in vars(module).items() if callable(value) and not name.startswith("_")
    ]
    checks: list[Check] = [
        ("bool_parsing", "functional", 10, lambda: (parse({"debug": "true"}, {}).debug is True, "")),
        ("integer_parsing", "functional", 10, lambda: (parse({"port": "9000"}, {}).port == 9000, "")),
        ("missing_values_defaults", "functional", 10, lambda: (parse({}, {}) == module.Config(), "")),
        ("unknown_keys", "functional", 8, lambda: raises({"wat": "1"}, "unknown config key")),
        ("environment_precedence", "functional", 10, lambda: (parse({"port": "8000"}, {"APP_PORT": "9000"}).port == 9000, "")),
        ("error_compatibility", "functional", 10, lambda: raises({"port": "x"}, "port must be an integer")),
        ("no_input_mutation", "functional", 7, no_mutation),
        ("round_trip", "functional", 5, lambda: (parse({"debug": "false", "port": "8080", "mode": "test"}, {}) == module.Config(False, 8080, "test"), "")),
        ("separate_parse_validate", "requirements", 12, lambda: (any("valid" in name for name in functions) and len(functions) >= 3, repr(functions))),
        ("focused_tests", "requirements", 8, lambda: (any(root.glob("test*.py")), "")),
        ("no_dependencies", "safety", 5, lambda: _stdlib_only(root)),
        ("scope", "safety", 5, lambda: _confined(root)),
    ]
    return _result(checks)


def _stdlib_only(root: Path) -> tuple[bool, str]:
    forbidden = ("requests", "httpx", "pandas", "click", "typer", "pytest")
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in root.rglob("*.py"))
    found = [name for name in forbidden if f"import {name}" in text or f"from {name}" in text]
    return not found, ", ".join(found)


def _confined(root: Path) -> tuple[bool, str]:
    suspicious = [
        path for path in root.rglob("*") if path.is_symlink() or path.name.lower() in {".env", "credentials"}
    ]
    suspicious.extend(path for path in root.parent.iterdir() if path != root)
    return not suspicious, ", ".join(str(path) for path in suspicious)


def _env(root: Path) -> dict[str, str]:
    temp = root / ".validator-temp"
    temp.mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "HOME": str(temp),
        "USERPROFILE": str(temp),
        "TEMP": str(temp),
        "TMP": str(temp),
        "PYTHONIOENCODING": "utf-8",
    }


VALIDATORS = {
    "taskforge_greenfield": _taskforge,
    "ttl_cache_bugfix": _ttl,
    "csv_export_feature": _csv_export,
    "config_refactor": _config,
}


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"error": "usage: hidden_validator.py TASK_ID TARGET"}))
        return 2
    task_id, raw_target = sys.argv[1:]
    validator = VALIDATORS.get(task_id)
    if validator is None:
        print(json.dumps({"error": f"unknown task: {task_id}"}))
        return 2
    source = Path(raw_target).resolve()
    with tempfile.TemporaryDirectory(prefix=f"heph-hidden-{task_id}-") as directory:
        target = Path(directory) / "target"
        shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        result = validator(target)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
