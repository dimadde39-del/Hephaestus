"""CLI launcher and doctor helpers for Hephaestus Studio."""

from __future__ import annotations

import importlib.util
import socket
import sqlite3
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from hephaestus.policy.repository import PolicyRepository
from hephaestus.storage.sqlite import init_database
from hephaestus.studio.security import (
    DEFAULT_STUDIO_HOST,
    DEFAULT_STUDIO_PORT,
    repository_root_from_module,
    resolve_static_dir,
    studio_url,
)
from hephaestus.studio.services import StudioService


@dataclass(frozen=True)
class StudioDoctorCheck:
    """One Studio doctor check."""

    name: str
    status: str
    detail: str


def run_studio(
    *,
    host: str = DEFAULT_STUDIO_HOST,
    port: int = DEFAULT_STUDIO_PORT,
    open_browser: bool = True,
    database_path: Path | str | None = None,
) -> None:
    """Start the local Studio backend and static frontend server."""

    _require_studio_dependencies()
    import uvicorn

    from hephaestus.studio.app import create_studio_app

    url = studio_url(host, port)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    app = create_studio_app(database_path, host=host, port=port)
    uvicorn.run(app, host=host, port=port, log_level="info")


def studio_doctor(
    *,
    host: str = DEFAULT_STUDIO_HOST,
    port: int = DEFAULT_STUDIO_PORT,
    database_path: Path | str | None = None,
) -> list[StudioDoctorCheck]:
    """Return local Studio readiness checks."""

    checks: list[StudioDoctorCheck] = []
    dependency_details: list[str] = []
    dependencies_ok = True
    for module in ("fastapi", "uvicorn"):
        installed = importlib.util.find_spec(module) is not None
        dependencies_ok = dependencies_ok and installed
        dependency_details.append(f"{module}: {'installed' if installed else 'missing'}")
    checks.append(
        StudioDoctorCheck(
            "Studio optional dependencies",
            "ok" if dependencies_ok else "missing",
            ", ".join(dependency_details),
        )
    )

    frontend_root = repository_root_from_module(__file__) / "apps" / "studio"
    package_json = frontend_root / "package.json"
    checks.append(
        StudioDoctorCheck(
            "Frontend source",
            "ok" if package_json.exists() else "missing",
            str(package_json),
        )
    )
    static_dir = resolve_static_dir(__file__)
    checks.append(
        StudioDoctorCheck(
            "Static asset availability",
            "ok" if static_dir is not None else "warn",
            str(static_dir or (frontend_root / "out")),
        )
    )

    try:
        db_path = init_database(database_path)
        checks.append(StudioDoctorCheck("Database access", "ok", str(db_path)))
    except sqlite3.Error as error:
        checks.append(StudioDoctorCheck("Database access", "error", str(error)))

    service = StudioService(database_path, static_assets_available=static_dir is not None)
    provider = service.provider_status()
    checks.append(
        StudioDoctorCheck(
            "Active provider",
            "ok" if provider.active_provider == "local/fake" else "configured",
            provider.active_label,
        )
    )
    policy = PolicyRepository(database_path).get_active_profile()
    checks.append(
        StudioDoctorCheck(
            "Active policy profile",
            "ok",
            f"{policy.name} ({policy.profile_type.value})",
        )
    )
    checks.append(
        StudioDoctorCheck(
            "Port availability",
            "ok" if is_port_available(host, port) else "busy",
            f"{studio_url(host, port)}",
        )
    )
    return checks


def is_port_available(host: str, port: int) -> bool:
    """Return whether a TCP port can be bound locally."""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
    except OSError:
        return False
    return True


def _require_studio_dependencies() -> None:
    missing = [
        module
        for module in ("fastapi", "uvicorn")
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Studio dependencies are missing: {joined}. Install with `uv sync --extra studio`."
        )

