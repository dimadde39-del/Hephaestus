"""Small JSON task tracker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("tasks.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("text")
    commands.add_parser("list")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = load(args.data)
    if args.command == "add":
        next_id = max((int(row["id"]) for row in rows), default=0) + 1
        rows.append({"id": next_id, "text": args.text, "done": False})
        save(args.data, rows)
        return 0
    for row in sorted(rows, key=lambda item: int(item["id"])):
        print(f"{row['id']}: {row['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
