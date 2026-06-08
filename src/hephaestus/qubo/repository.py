"""SQLite persistence for QUBO problems and solutions."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from hephaestus.qubo.schemas import QuboProblem, QuboSolution
from hephaestus.storage.sqlite import connect_database, init_database


class QuboRepository:
    """Persist and read QUBO formulations and local solver results."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def save_problem(self, problem: QuboProblem) -> QuboProblem:
        """Persist a complete QUBO problem."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO qubo_problems (
                    id, run_id, problem_type, source_benchmark_id, source_frontier_id,
                    source_decision_trace_ids_json, variable_count, linear_term_count,
                    quadratic_term_count, constraint_count, tags_json, created_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    problem.id,
                    problem.run_id,
                    problem.problem_type.value,
                    problem.source_benchmark_id,
                    problem.source_frontier_id,
                    _json_dumps(problem.source_decision_trace_ids),
                    len(problem.variables),
                    len(problem.linear_terms),
                    len(problem.quadratic_terms),
                    len(problem.constraints),
                    _json_dumps(problem.tags),
                    _datetime_to_text(problem.created_at),
                    problem.model_dump_json(),
                ),
            )
        return problem

    def save_solution(self, solution: QuboSolution, problem: QuboProblem | None = None) -> QuboSolution:
        """Persist a solver result for a QUBO problem."""

        run_id = problem.run_id if problem is not None else self._run_id_for_problem(solution.problem_id)
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO qubo_solutions (
                    id, problem_id, run_id, solver_name, objective_value, feasible,
                    iterations, selected_variables_json, constraint_violations_json,
                    created_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    solution.id,
                    solution.problem_id,
                    run_id,
                    solution.solver_name,
                    solution.objective_value,
                    int(solution.feasible),
                    solution.iterations,
                    _json_dumps(solution.selected_variables),
                    _json_dumps(solution.constraint_violations),
                    _datetime_to_text(solution.created_at),
                    solution.model_dump_json(),
                ),
            )
        return solution

    def list_problems(
        self,
        *,
        run_id: str | None = None,
        limit: int = 20,
    ) -> list[QuboProblem]:
        """List persisted QUBO problems newest-first."""

        with connect_database(self.database_path) as connection:
            if run_id is None:
                rows = connection.execute(
                    """
                    SELECT raw_json FROM qubo_problems
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT raw_json FROM qubo_problems
                    WHERE run_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (run_id, limit),
                ).fetchall()
        return [QuboProblem.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def get_problem(self, problem_id: str) -> QuboProblem | None:
        """Read one QUBO problem by ID."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM qubo_problems WHERE id = ?",
                (problem_id,),
            ).fetchone()
        if row is None:
            return None
        return QuboProblem.model_validate_json(_row_str(row, "raw_json"))

    def list_solutions_for_problem(self, problem_id: str) -> list[QuboSolution]:
        """List all persisted solutions for one problem."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM qubo_solutions
                WHERE problem_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (problem_id,),
            ).fetchall()
        return [QuboSolution.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def get_latest_solution(self, problem_id: str) -> QuboSolution | None:
        """Return the latest solution for a problem, if any."""

        solutions = self.list_solutions_for_problem(problem_id)
        return solutions[0] if solutions else None

    def list_solutions_by_run(self, run_id: str) -> list[QuboSolution]:
        """List all QUBO solutions associated with one run."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM qubo_solutions
                WHERE run_id = ?
                ORDER BY created_at, id
                """,
                (run_id,),
            ).fetchall()
        return [QuboSolution.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def _run_id_for_problem(self, problem_id: str) -> str | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT run_id FROM qubo_problems WHERE id = ?",
                (problem_id,),
            ).fetchone()
        if row is None:
            return None
        return cast(str | None, row["run_id"])


def _datetime_to_text(value: object) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])
