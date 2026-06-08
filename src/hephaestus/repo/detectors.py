"""Read-only repository signal detectors."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from hephaestus.repo.risk import build_command_risk_signals, classify_command, classify_script
from hephaestus.repo.schemas import (
    CiProviderInfo,
    CommandRiskCategory,
    PackageManagerInfo,
    RepoFileSignal,
    RiskSignal,
    ScriptCommand,
    TestCommand,
)


@dataclass(frozen=True)
class DetectionResult:
    """Aggregate repo signals produced by detector functions."""

    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    package_managers: list[PackageManagerInfo] = field(default_factory=list)
    scripts: list[ScriptCommand] = field(default_factory=list)
    test_commands: list[TestCommand] = field(default_factory=list)
    build_commands: list[TestCommand] = field(default_factory=list)
    lint_commands: list[TestCommand] = field(default_factory=list)
    ci_providers: list[CiProviderInfo] = field(default_factory=list)
    docker_detected: bool = False
    env_files_detected: list[str] = field(default_factory=list)
    risk_signals: list[RiskSignal] = field(default_factory=list)
    file_signals: list[RepoFileSignal] = field(default_factory=list)


def detect_repository(root: Path) -> DetectionResult:
    """Detect supported repository ecosystems using read-only file inspection."""

    root = root.resolve()
    file_signals: list[RepoFileSignal] = []
    languages: list[str] = []
    frameworks: list[str] = []
    tools: list[str] = []
    managers: list[PackageManagerInfo] = []
    scripts: list[ScriptCommand] = []
    test_commands: list[TestCommand] = []
    build_commands: list[TestCommand] = []
    lint_commands: list[TestCommand] = []
    ci_providers: list[CiProviderInfo] = []

    node = _detect_node(root, file_signals)
    languages.extend(node.languages)
    frameworks.extend(node.frameworks)
    tools.extend(node.tools)
    managers.extend(node.package_managers)
    scripts.extend(node.scripts)
    test_commands.extend(node.test_commands)
    build_commands.extend(node.build_commands)
    lint_commands.extend(node.lint_commands)

    python = _detect_python(root, file_signals)
    languages.extend(python.languages)
    frameworks.extend(python.frameworks)
    tools.extend(python.tools)
    managers.extend(python.package_managers)
    test_commands.extend(python.test_commands)
    build_commands.extend(python.build_commands)
    lint_commands.extend(python.lint_commands)

    rust = _detect_rust(root, file_signals)
    languages.extend(rust.languages)
    tools.extend(rust.tools)
    managers.extend(rust.package_managers)
    test_commands.extend(rust.test_commands)
    build_commands.extend(rust.build_commands)
    lint_commands.extend(rust.lint_commands)

    go = _detect_go(root, file_signals)
    languages.extend(go.languages)
    tools.extend(go.tools)
    managers.extend(go.package_managers)
    test_commands.extend(go.test_commands)
    build_commands.extend(go.build_commands)

    docker_detected, docker_signals = _detect_docker(root)
    file_signals.extend(docker_signals)
    ci_providers.extend(_detect_ci(root, file_signals))
    env_files = _detect_env_files(root)
    file_signals.extend(
        RepoFileSignal(
            path=env_file,
            signal_type="env",
            detected_as="environment file",
            confidence=0.9,
            notes=["Detected by filename only; contents were not inspected."],
        )
        for env_file in env_files
    )

    risk_signals = [
        *build_command_risk_signals(scripts),
        *_repo_risk_signals(
            env_files=env_files,
            scripts=scripts,
            managers=managers,
            test_commands=test_commands,
            has_ci=bool(ci_providers),
        ),
    ]

    return DetectionResult(
        languages=_dedupe(languages),
        frameworks=_dedupe(frameworks),
        tools=_dedupe(tools),
        package_managers=_dedupe_managers(managers),
        scripts=scripts,
        test_commands=_dedupe_commands(test_commands),
        build_commands=_dedupe_commands(build_commands),
        lint_commands=_dedupe_commands(lint_commands),
        ci_providers=ci_providers,
        docker_detected=docker_detected,
        env_files_detected=_dedupe(env_files),
        risk_signals=risk_signals,
        file_signals=file_signals,
    )


def _detect_node(root: Path, file_signals: list[RepoFileSignal]) -> DetectionResult:
    package_json_path = root / "package.json"
    if not package_json_path.exists():
        return DetectionResult()

    file_signals.append(_signal("package.json", "manifest", "Node package manifest"))
    package_json = _read_json_object(package_json_path)
    managers = _node_package_managers(root, package_json, file_signals)
    primary_manager = managers[0].name if managers else "npm"
    package_names = _package_names(package_json)
    scripts = _node_scripts(package_json, primary_manager)
    frameworks = _node_frameworks(root, package_names, file_signals)
    tools = _node_tools(root, package_names, file_signals)
    test_commands = _commands_for_scripts(scripts, "test")
    build_commands = _commands_for_scripts(scripts, "build")
    lint_commands = [
        *_commands_for_scripts(scripts, "lint"),
        *_commands_for_scripts(scripts, "typecheck"),
        *_commands_for_scripts(scripts, "check"),
    ]

    languages = ["JavaScript"]
    if (root / "tsconfig.json").exists() or "typescript" in package_names:
        languages.append("TypeScript")
    if "react" in package_names or "React" in frameworks:
        frameworks.append("React")

    return DetectionResult(
        languages=languages,
        frameworks=_dedupe(frameworks),
        tools=_dedupe(tools),
        package_managers=managers,
        scripts=scripts,
        test_commands=test_commands,
        build_commands=build_commands,
        lint_commands=_dedupe_commands(lint_commands),
    )


def _node_package_managers(
    root: Path,
    package_json: dict[str, Any],
    file_signals: list[RepoFileSignal],
) -> list[PackageManagerInfo]:
    detected: list[PackageManagerInfo] = []
    package_manager_value = str(package_json.get("packageManager", ""))
    package_manager_name = package_manager_value.split("@", 1)[0] if package_manager_value else ""
    lockfiles = [
        ("pnpm", "pnpm-lock.yaml"),
        ("yarn", "yarn.lock"),
        ("npm", "package-lock.json"),
        ("bun", "bun.lockb"),
        ("bun", "bun.lock"),
    ]
    for name, lockfile in lockfiles:
        if (root / lockfile).exists():
            file_signals.append(_signal(lockfile, "lockfile", f"{name} lockfile"))
            detected.append(
                PackageManagerInfo(
                    name=name,
                    ecosystem="node",
                    manifest_path="package.json",
                    lockfile_path=lockfile,
                    command_prefix=name,
                    confidence=0.95,
                )
            )
    if package_manager_name and not any(manager.name == package_manager_name for manager in detected):
        detected.insert(
            0,
            PackageManagerInfo(
                name=package_manager_name,
                ecosystem="node",
                manifest_path="package.json",
                command_prefix=package_manager_name,
                confidence=0.9,
            ),
        )
    if not detected:
        detected.append(
            PackageManagerInfo(
                name="npm",
                ecosystem="node",
                manifest_path="package.json",
                command_prefix="npm",
                confidence=0.65,
            )
        )
    return _dedupe_managers(detected)


def _node_scripts(package_json: dict[str, Any], manager: str) -> list[ScriptCommand]:
    scripts_value = package_json.get("scripts", {})
    if not isinstance(scripts_value, dict):
        return []
    scripts: list[ScriptCommand] = []
    for script_name, raw in sorted(scripts_value.items()):
        raw_command = str(raw)
        scripts.append(
            classify_script(
                name=str(script_name),
                command=_node_script_command(manager, str(script_name)),
                source="package.json#scripts",
                package_manager=manager,
                raw_command=raw_command,
            )
        )
    return scripts


def _node_script_command(manager: str, script_name: str) -> str:
    if manager == "npm" and script_name not in {"test", "start", "stop", "restart"}:
        return f"npm run {script_name}"
    return f"{manager} {script_name}"


def _node_frameworks(
    root: Path,
    package_names: set[str],
    file_signals: list[RepoFileSignal],
) -> list[str]:
    frameworks: list[str] = []
    config_frameworks = [
        (("next.config.js", "next.config.ts", "next.config.mjs"), "Next.js"),
        (("vite.config.js", "vite.config.ts", "vite.config.mjs"), "Vite"),
    ]
    for filenames, framework in config_frameworks:
        for filename in filenames:
            if (root / filename).exists():
                file_signals.append(_signal(filename, "config", f"{framework} config"))
                frameworks.append(framework)
                break
    if "next" in package_names:
        frameworks.append("Next.js")
    if "vite" in package_names:
        frameworks.append("Vite")
    if "react" in package_names:
        frameworks.append("React")
    if "tailwindcss" in package_names:
        frameworks.append("Tailwind")
    if "fastify" in package_names:
        frameworks.append("Fastify")
    return _dedupe(frameworks)


def _node_tools(
    root: Path,
    package_names: set[str],
    file_signals: list[RepoFileSignal],
) -> list[str]:
    tools: list[str] = []
    config_tools = [
        (("tsconfig.json",), "TypeScript"),
        (("tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs"), "Tailwind"),
        (
            (
                ".eslintrc",
                ".eslintrc.js",
                ".eslintrc.cjs",
                ".eslintrc.json",
                "eslint.config.js",
                "eslint.config.mjs",
                "eslint.config.ts",
            ),
            "ESLint",
        ),
        (("vitest.config.js", "vitest.config.ts", "vitest.config.mjs"), "Vitest"),
        (("jest.config.js", "jest.config.ts", "jest.config.cjs", "jest.config.mjs"), "Jest"),
    ]
    for filenames, tool in config_tools:
        for filename in filenames:
            if (root / filename).exists():
                file_signals.append(_signal(filename, "config", f"{tool} config"))
                tools.append(tool)
                break
    if "typescript" in package_names:
        tools.append("TypeScript")
    if "tailwindcss" in package_names:
        tools.append("Tailwind")
    if "eslint" in package_names:
        tools.append("ESLint")
    if "vitest" in package_names:
        tools.append("Vitest")
    if "jest" in package_names:
        tools.append("Jest")
    return _dedupe(tools)


def _detect_python(root: Path, file_signals: list[RepoFileSignal]) -> DetectionResult:
    pyproject_path = root / "pyproject.toml"
    requirements_path = root / "requirements.txt"
    setup_path = root / "setup.py"
    if not pyproject_path.exists() and not requirements_path.exists() and not setup_path.exists():
        return DetectionResult()

    package_data = _read_toml_object(pyproject_path) if pyproject_path.exists() else {}
    if pyproject_path.exists():
        file_signals.append(_signal("pyproject.toml", "manifest", "Python project manifest"))
    if requirements_path.exists():
        file_signals.append(_signal("requirements.txt", "manifest", "pip requirements"))
    if setup_path.exists():
        file_signals.append(_signal("setup.py", "manifest", "setuptools script"))

    managers = _python_package_managers(root, package_data, file_signals)
    package_names = _python_package_names(root, package_data)
    tools = _python_tools(root, package_data, package_names, file_signals)
    frameworks = _python_frameworks(package_names)
    prefix = _python_prefix(managers)
    test_commands = _python_test_commands(root, package_data, package_names, prefix)
    lint_commands = _python_lint_commands(package_data, package_names, prefix)

    return DetectionResult(
        languages=["Python"],
        frameworks=frameworks,
        tools=tools,
        package_managers=managers,
        test_commands=test_commands,
        lint_commands=lint_commands,
    )


def _python_package_managers(
    root: Path,
    package_data: dict[str, Any],
    file_signals: list[RepoFileSignal],
) -> list[PackageManagerInfo]:
    managers: list[PackageManagerInfo] = []
    if (root / "uv.lock").exists() or _nested_dict(package_data, "tool", "uv"):
        if (root / "uv.lock").exists():
            file_signals.append(_signal("uv.lock", "lockfile", "uv lockfile"))
        managers.append(
            PackageManagerInfo(
                name="uv",
                ecosystem="python",
                manifest_path="pyproject.toml" if (root / "pyproject.toml").exists() else "",
                lockfile_path="uv.lock" if (root / "uv.lock").exists() else "",
                command_prefix="uv run",
                confidence=0.95,
            )
        )
    if (root / "poetry.lock").exists() or _nested_dict(package_data, "tool", "poetry"):
        if (root / "poetry.lock").exists():
            file_signals.append(_signal("poetry.lock", "lockfile", "Poetry lockfile"))
        managers.append(
            PackageManagerInfo(
                name="poetry",
                ecosystem="python",
                manifest_path="pyproject.toml" if (root / "pyproject.toml").exists() else "",
                lockfile_path="poetry.lock" if (root / "poetry.lock").exists() else "",
                command_prefix="poetry run",
                confidence=0.9,
            )
        )
    if (root / "requirements.txt").exists() or (root / "setup.py").exists():
        managers.append(
            PackageManagerInfo(
                name="pip",
                ecosystem="python",
                manifest_path="requirements.txt" if (root / "requirements.txt").exists() else "setup.py",
                command_prefix="python -m",
                confidence=0.75,
            )
        )
    if not managers and (root / "pyproject.toml").exists():
        managers.append(
            PackageManagerInfo(
                name="python",
                ecosystem="python",
                manifest_path="pyproject.toml",
                command_prefix="python -m",
                confidence=0.6,
            )
        )
    return _dedupe_managers(managers)


def _python_package_names(root: Path, package_data: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    project = _as_dict(package_data.get("project"))
    names.update(_dependency_names(project.get("dependencies", [])))
    optional_dependencies = _as_dict(project.get("optional-dependencies"))
    for dependencies in optional_dependencies.values():
        names.update(_dependency_names(dependencies))
    dependency_groups = _as_dict(package_data.get("dependency-groups"))
    for dependencies in dependency_groups.values():
        names.update(_dependency_names(dependencies))
    poetry = _nested_dict(package_data, "tool", "poetry")
    names.update(_as_dict(poetry.get("dependencies")).keys())
    names.update(_as_dict(poetry.get("dev-dependencies")).keys())
    requirements_path = root / "requirements.txt"
    if requirements_path.exists():
        names.update(_requirements_names(requirements_path))
    return {name.lower() for name in names}


def _python_tools(
    root: Path,
    package_data: dict[str, Any],
    package_names: set[str],
    file_signals: list[RepoFileSignal],
) -> list[str]:
    tools: list[str] = []
    if (root / "pytest.ini").exists() or _nested_dict(package_data, "tool", "pytest"):
        file_signals.append(_signal("pytest.ini" if (root / "pytest.ini").exists() else "pyproject.toml", "config", "pytest config"))
        tools.append("pytest")
    if (root / "tox.ini").exists():
        file_signals.append(_signal("tox.ini", "config", "tox config"))
        tools.append("tox")
    if _nested_dict(package_data, "tool", "ruff") or "ruff" in package_names:
        tools.append("ruff")
    if _nested_dict(package_data, "tool", "mypy") or "mypy" in package_names:
        tools.append("mypy")
    if "pytest" in package_names:
        tools.append("pytest")
    return _dedupe(tools)


def _python_frameworks(package_names: set[str]) -> list[str]:
    frameworks: list[str] = []
    if "fastapi" in package_names:
        frameworks.append("FastAPI")
    if "django" in package_names:
        frameworks.append("Django")
    if "flask" in package_names:
        frameworks.append("Flask")
    return frameworks


def _python_test_commands(
    root: Path,
    package_data: dict[str, Any],
    package_names: set[str],
    prefix: str,
) -> list[TestCommand]:
    if (
        "pytest" not in package_names
        and not (root / "pytest.ini").exists()
        and not _nested_dict(package_data, "tool", "pytest")
    ):
        return []
    return [_test_command(_prefix_command(prefix, "pytest"), "python", "pytest")]


def _python_lint_commands(
    package_data: dict[str, Any],
    package_names: set[str],
    prefix: str,
) -> list[TestCommand]:
    commands: list[TestCommand] = []
    if _nested_dict(package_data, "tool", "ruff") or "ruff" in package_names:
        commands.append(_test_command(_prefix_command(prefix, "ruff check ."), "python", "ruff"))
    if _nested_dict(package_data, "tool", "mypy") or "mypy" in package_names:
        commands.append(_test_command(_prefix_command(prefix, "mypy"), "python", "mypy"))
    return commands


def _python_prefix(managers: list[PackageManagerInfo]) -> str:
    names = [manager.name for manager in managers]
    if "uv" in names:
        return "uv run"
    if "poetry" in names:
        return "poetry run"
    return "python -m"


def _detect_rust(root: Path, file_signals: list[RepoFileSignal]) -> DetectionResult:
    cargo_toml = root / "Cargo.toml"
    if not cargo_toml.exists():
        return DetectionResult()
    file_signals.append(_signal("Cargo.toml", "manifest", "Rust Cargo manifest"))
    if (root / "Cargo.lock").exists():
        file_signals.append(_signal("Cargo.lock", "lockfile", "Cargo lockfile"))
    manager = PackageManagerInfo(
        name="cargo",
        ecosystem="rust",
        manifest_path="Cargo.toml",
        lockfile_path="Cargo.lock" if (root / "Cargo.lock").exists() else "",
        command_prefix="cargo",
        confidence=0.95,
    )
    return DetectionResult(
        languages=["Rust"],
        tools=["cargo"],
        package_managers=[manager],
        test_commands=[_test_command("cargo test", "rust", "cargo")],
        build_commands=[
            _test_command("cargo check", "rust", "cargo"),
            _test_command("cargo build", "rust", "cargo"),
        ],
        lint_commands=[
            _test_command("cargo fmt --check", "rust", "rustfmt"),
            _test_command("cargo clippy", "rust", "clippy"),
        ],
    )


def _detect_go(root: Path, file_signals: list[RepoFileSignal]) -> DetectionResult:
    go_mod = root / "go.mod"
    if not go_mod.exists():
        return DetectionResult()
    file_signals.append(_signal("go.mod", "manifest", "Go module manifest"))
    if (root / "go.sum").exists():
        file_signals.append(_signal("go.sum", "lockfile", "Go checksum file"))
    manager = PackageManagerInfo(
        name="go",
        ecosystem="go",
        manifest_path="go.mod",
        lockfile_path="go.sum" if (root / "go.sum").exists() else "",
        command_prefix="go",
        confidence=0.95,
    )
    return DetectionResult(
        languages=["Go"],
        tools=["go"],
        package_managers=[manager],
        test_commands=[_test_command("go test ./...", "go", "go test")],
        build_commands=[_test_command("go build ./...", "go", "go build")],
    )


def _detect_docker(root: Path) -> tuple[bool, list[RepoFileSignal]]:
    signals: list[RepoFileSignal] = []
    for filename in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        if (root / filename).exists():
            signals.append(_signal(filename, "container", "Docker configuration"))
    return bool(signals), signals


def _detect_ci(root: Path, file_signals: list[RepoFileSignal]) -> list[CiProviderInfo]:
    providers: list[CiProviderInfo] = []
    github_dir = root / ".github" / "workflows"
    if github_dir.exists():
        workflow_paths = sorted(
            path
            for pattern in ("*.yml", "*.yaml")
            for path in github_dir.glob(pattern)
            if path.is_file()
        )
        if workflow_paths:
            relative_paths = [_relative(path, root) for path in workflow_paths]
            file_signals.extend(
                _signal(path, "ci", "GitHub Actions workflow") for path in relative_paths
            )
            providers.append(
                CiProviderInfo(
                    provider="GitHub Actions",
                    config_paths=relative_paths,
                    workflow_names=[path.stem for path in workflow_paths],
                    confidence=0.95,
                )
            )
    gitlab = root / ".gitlab-ci.yml"
    if gitlab.exists():
        file_signals.append(_signal(".gitlab-ci.yml", "ci", "GitLab CI pipeline"))
        providers.append(
            CiProviderInfo(
                provider="GitLab CI",
                config_paths=[".gitlab-ci.yml"],
                workflow_names=["gitlab-ci"],
                confidence=0.95,
            )
        )
    return providers


def _detect_env_files(root: Path) -> list[str]:
    env_files = [
        _relative(path, root)
        for path in sorted(root.glob(".env*"))
        if path.is_file() and path.name not in {".envrc"}
    ]
    return _dedupe(env_files)


def _repo_risk_signals(
    *,
    env_files: list[str],
    scripts: list[ScriptCommand],
    managers: list[PackageManagerInfo],
    test_commands: list[TestCommand],
    has_ci: bool,
) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    sensitive_env_files = [
        env_file
        for env_file in env_files
        if not any(marker in env_file.lower() for marker in ("example", "sample", "template"))
    ]
    if sensitive_env_files:
        signals.append(
            RiskSignal(
                level=CommandRiskCategory.HIGH_RISK,
                category="environment",
                summary="Environment files are present and should not be exposed or modified casually.",
                evidence=sensitive_env_files,
                mitigation="Inspect names only unless the user explicitly asks to review contents.",
            )
        )
    package_manager_keys = {(manager.ecosystem, manager.name) for manager in managers}
    ecosystems = {manager.ecosystem for manager in managers}
    for ecosystem in ecosystems:
        manager_names = sorted(name for manager_ecosystem, name in package_manager_keys if manager_ecosystem == ecosystem)
        if len(manager_names) > 1:
            signals.append(
                RiskSignal(
                    level=CommandRiskCategory.MEDIUM_RISK,
                    category="package_manager",
                    summary=f"Multiple {ecosystem} package managers were detected.",
                    evidence=manager_names,
                    mitigation="Prefer the lockfile-backed manager before suggesting validation commands.",
                )
            )
    if managers and not test_commands:
        signals.append(
            RiskSignal(
                level=CommandRiskCategory.MEDIUM_RISK,
                category="validation",
                summary="No test command was detected.",
                evidence=[manager.name for manager in managers],
                mitigation="Generate a release task to identify or add a validation command.",
            )
        )
    if not has_ci and managers:
        signals.append(
            RiskSignal(
                level=CommandRiskCategory.MEDIUM_RISK,
                category="ci",
                summary="No CI provider was detected.",
                evidence=[manager.ecosystem for manager in managers],
                mitigation="Treat local validation as the primary release-readiness evidence.",
            )
        )
    deploy_scripts = [
        script.name for script in scripts if any(term in script.name.lower() for term in ("deploy", "publish", "release"))
    ]
    if deploy_scripts:
        signals.append(
            RiskSignal(
                level=CommandRiskCategory.EXTERNAL_SIDE_EFFECT,
                category="release",
                summary="Release or deployment scripts exist in package metadata.",
                evidence=deploy_scripts,
                mitigation="Require approval before running release, publish, or deploy scripts.",
            )
        )
    return signals


def _commands_for_scripts(scripts: list[ScriptCommand], keyword: str) -> list[TestCommand]:
    commands: list[TestCommand] = []
    for script in scripts:
        lowered_name = script.name.lower()
        if keyword not in lowered_name:
            continue
        commands.append(
            TestCommand(
                command=script.command,
                source=script.source,
                framework=_framework_for_script(script),
                classification=script.classification,
                reasons=script.reasons,
                requires_approval=script.requires_approval,
            )
        )
    return commands


def _test_command(command: str, source: str, framework: str) -> TestCommand:
    classification, reasons, requires_approval = classify_command(command)
    return TestCommand(
        command=command,
        source=source,
        framework=framework,
        classification=classification,
        reasons=reasons,
        requires_approval=requires_approval,
    )


def _prefix_command(prefix: str, command: str) -> str:
    if prefix == "python -m" and command in {"ruff check .", "mypy"}:
        return command
    return f"{prefix} {command}".strip()


def _framework_for_script(script: ScriptCommand) -> str:
    raw = script.raw_command.lower()
    if "vitest" in raw:
        return "Vitest"
    if "jest" in raw:
        return "Jest"
    if "eslint" in raw:
        return "ESLint"
    if "next" in raw:
        return "Next.js"
    if "vite" in raw:
        return "Vite"
    return script.package_manager


def _package_names(package_json: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        value = package_json.get(key, {})
        if isinstance(value, dict):
            names.update(str(name).lower() for name in value)
    return names


def _dependency_names(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    names: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip().split(";", 1)[0].split("[", 1)[0]
        for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            normalized = normalized.split(separator, 1)[0]
        if normalized:
            names.add(normalized.lower())
    return names


def _requirements_names(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-")):
            continue
        names.update(_dependency_names([stripped]))
    return names


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_toml_object(path: Path) -> dict[str, Any]:
    try:
        loaded = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _nested_dict(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key, {})
    return current if isinstance(current, dict) else {}


def _as_dict(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _signal(path: str, signal_type: str, detected_as: str) -> RepoFileSignal:
    return RepoFileSignal(path=path, signal_type=signal_type, detected_as=detected_as)


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _dedupe_managers(managers: list[PackageManagerInfo]) -> list[PackageManagerInfo]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[PackageManagerInfo] = []
    for manager in managers:
        key = (manager.ecosystem, manager.name, manager.lockfile_path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(manager)
    return deduped


def _dedupe_commands(commands: list[TestCommand]) -> list[TestCommand]:
    seen: set[str] = set()
    deduped: list[TestCommand] = []
    for command in commands:
        if command.command in seen:
            continue
        seen.add(command.command)
        deduped.append(command)
    return deduped
