"""SQLite connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hephaestus.storage.migrations import run_migrations


def get_default_database_path() -> Path:
    """Return the default per-working-directory database path."""

    return Path.cwd() / ".hephaestus" / "hephaestus.db"


def connect_database(database_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with local Hephaestus defaults."""

    path = Path(database_path) if database_path is not None else get_default_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database(database_path: Path | str | None = None) -> Path:
    """Initialize the SQLite database and return its path."""

    path = Path(database_path) if database_path is not None else get_default_database_path()
    with connect_database(path) as connection:
        run_migrations(connection)
    return path
