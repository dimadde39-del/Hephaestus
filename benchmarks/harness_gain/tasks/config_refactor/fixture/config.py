"""Application configuration parsing."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    debug: bool = False
    port: int = 8080
    mode: str = "dev"


def parse_config(
    values: Mapping[str, str],
    environ: Mapping[str, str] | None = None,
) -> Config:
    source = dict(values)
    env = os.environ if environ is None else environ
    for key in ("debug", "port", "mode"):
        override = env.get(f"APP_{key.upper()}")
        if override is not None:
            source[key] = override
    unknown = sorted(set(source) - {"debug", "port", "mode"})
    if unknown:
        raise ValueError(f"unknown config key: {unknown[0]}")
    debug_raw = source.get("debug", "false").lower()
    if debug_raw not in {"true", "false"}:
        raise ValueError("debug must be true or false")
    try:
        port = int(source.get("port", "8080"))
    except ValueError as error:
        raise ValueError("port must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    mode = source.get("mode", "dev")
    if mode not in {"dev", "prod", "test"}:
        raise ValueError("mode must be dev, prod, or test")
    return Config(debug=debug_raw == "true", port=port, mode=mode)

