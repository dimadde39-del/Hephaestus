"""Frozen benchmark task catalogue and fixture helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    prompt: str
    self_test_command: tuple[str, ...] = ("python", "-m", "unittest", "discover", "-v")

    @property
    def source_dir(self) -> Path:
        return Path(__file__).parent / "tasks" / self.task_id

    @property
    def fixture_dir(self) -> Path:
        return self.source_dir / "fixture"


TASKFORGE_PROMPT = (
    'Создай небольшой Python CLI TaskForge. Команды: add "text", list, done <id>, delete <id>. '
    "Python 3.12. Только стандартная библиотека runtime. JSON persistence. Atomic JSON write. "
    "Пустая задача запрещена. Missing ID даёт понятную ошибку и ненулевой exit code. "
    "Повторный done безопасен. Добавь tests и README."
)

TASKS = {
    "taskforge_greenfield": TaskSpec("taskforge_greenfield", TASKFORGE_PROMPT),
    "ttl_cache_bugfix": TaskSpec(
        "ttl_cache_bugfix",
        "Исправь существующий TTLCache: expired keys are not returned; expired keys are removed; "
        "len excludes expired entries; ttl <= 0 is rejected; custom clock remains supported; "
        "public API remains compatible. Добавь focused tests. Не добавляй dependencies.",
    ),
    "csv_export_feature": TaskSpec(
        "csv_export_feature",
        "В существующий stdlib tracker добавь CSV export command: stable columns, correct CSV "
        "escaping, deterministic ordering, UTF-8, atomic output replacement и clear errors. "
        "Добавь tests и README example. Не добавляй dependencies.",
    ),
    "config_refactor": TaskSpec(
        "config_refactor",
        "В существующем config parser отдели parsing от validation, сохрани public API и "
        "supported values, улучши errors, добавь focused tests и избегай unnecessary abstractions.",
    ),
}


def get_task(task_id: str) -> TaskSpec:
    try:
        return TASKS[task_id]
    except KeyError as error:
        raise ValueError(f"Unknown benchmark task: {task_id}") from error

