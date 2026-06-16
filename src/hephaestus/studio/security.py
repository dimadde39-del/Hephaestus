"""Local-first security helpers for Hephaestus Studio."""

from __future__ import annotations

from pathlib import Path

DEFAULT_STUDIO_HOST = "127.0.0.1"
DEFAULT_STUDIO_PORT = 8741


def is_loopback_host(host: str) -> bool:
    """Return whether a bind host is local loopback."""

    return host in {"127.0.0.1", "localhost", "::1"}


def studio_url(host: str = DEFAULT_STUDIO_HOST, port: int = DEFAULT_STUDIO_PORT) -> str:
    """Build the user-facing local Studio URL."""

    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{display_host}:{port}"


def allowed_cors_origins(
    *,
    host: str = DEFAULT_STUDIO_HOST,
    port: int = DEFAULT_STUDIO_PORT,
) -> list[str]:
    """Return precise local origins for Studio and frontend development."""

    origins = {
        studio_url(host, port),
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    }
    for dev_port in (3000, 3001, 4173, 5173):
        origins.add(f"http://127.0.0.1:{dev_port}")
        origins.add(f"http://localhost:{dev_port}")
    return sorted(origins)


def repository_root_from_module(module_file: str) -> Path:
    """Resolve the repository root from a module file path."""

    return Path(module_file).resolve().parents[3]


def resolve_static_dir(module_file: str, static_dir: Path | str | None = None) -> Path | None:
    """Return the exported Studio frontend directory if it exists."""

    if static_dir is not None:
        path = Path(static_dir)
        return path if (path / "index.html").exists() else None
    candidate = repository_root_from_module(module_file) / "apps" / "studio" / "out"
    return candidate if (candidate / "index.html").exists() else None
