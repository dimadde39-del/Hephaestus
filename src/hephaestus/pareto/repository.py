"""SQLite persistence for Pareto frontiers and selections."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from hephaestus.pareto.schemas import (
    DecisionCandidate,
    ParetoFrontier,
    ParetoSelectionResult,
)
from hephaestus.storage.sqlite import connect_database, init_database


class ParetoRepository:
    """Persist and read Pareto decision frontiers."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def save_selection(self, selection: ParetoSelectionResult) -> ParetoSelectionResult:
        """Persist a complete Pareto selection result."""

        frontier = selection.frontier
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO pareto_frontiers (
                    id, run_id, title, candidate_type, preference_profile_id,
                    selected_candidate_id, candidate_count, frontier_count, dominated_count,
                    tradeoff_summary, created_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    frontier.id,
                    frontier.run_id,
                    frontier.title,
                    frontier.candidate_type.value if frontier.candidate_type is not None else "",
                    frontier.preference_profile_id,
                    frontier.selected_candidate_id,
                    len(frontier.candidates),
                    len(frontier.frontier_candidate_ids),
                    len(frontier.dominated_candidate_ids),
                    frontier.tradeoff_explanation.summary
                    if frontier.tradeoff_explanation is not None
                    else "",
                    _datetime_to_text(frontier.created_at),
                    frontier.model_dump_json(),
                ),
            )
            connection.execute(
                "DELETE FROM pareto_candidates WHERE frontier_id = ?",
                (frontier.id,),
            )
            for candidate in frontier.candidates:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO pareto_candidates (
                        id, frontier_id, candidate_id, run_id, candidate_type, label,
                        constraints_satisfied, objective_vector_json,
                        violated_constraints_json, estimated_cost, estimated_tokens,
                        rationale, source_decision_trace_ids_json, source_profile_ids_json,
                        tags_json, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"{frontier.id}:{candidate.id}",
                        frontier.id,
                        candidate.id,
                        frontier.run_id,
                        candidate.candidate_type.value,
                        candidate.label,
                        int(candidate.constraints_satisfied),
                        candidate.objective_vector.model_dump_json(),
                        _json_dumps(candidate.violated_constraints),
                        candidate.estimated_cost,
                        candidate.estimated_tokens,
                        candidate.rationale,
                        _json_dumps(candidate.source_decision_trace_ids),
                        _json_dumps(candidate.source_profile_ids),
                        _json_dumps(candidate.tags),
                        candidate.model_dump_json(),
                    ),
                )
            connection.execute(
                """
                INSERT OR REPLACE INTO pareto_selections (
                    id, frontier_id, run_id, selected_candidate_id,
                    preference_profile_id, preference_profile_json,
                    ranked_candidate_ids_json, candidate_scores_json,
                    tradeoff_json, created_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"selection_{frontier.id}",
                    frontier.id,
                    frontier.run_id,
                    selection.selected_candidate.id,
                    selection.preference_profile.id,
                    selection.preference_profile.model_dump_json(),
                    _json_dumps(selection.ranked_candidate_ids),
                    _json_dumps(selection.candidate_scores),
                    selection.tradeoff_explanation.model_dump_json(),
                    _datetime_to_text(frontier.created_at),
                    selection.model_dump_json(),
                ),
            )
        return selection

    def save_selections(
        self,
        selections: list[ParetoSelectionResult],
    ) -> list[ParetoSelectionResult]:
        """Persist several Pareto selection results."""

        return [self.save_selection(selection) for selection in selections]

    def get_selection(self, frontier_id: str) -> ParetoSelectionResult | None:
        """Read one complete selection by frontier ID."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM pareto_selections WHERE frontier_id = ?",
                (frontier_id,),
            ).fetchone()
        if row is None:
            return None
        return ParetoSelectionResult.model_validate_json(_row_str(row, "raw_json"))

    def get_frontier(self, frontier_id: str) -> ParetoFrontier | None:
        """Read one frontier by ID."""

        selection = self.get_selection(frontier_id)
        if selection is not None:
            return selection.frontier
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM pareto_frontiers WHERE id = ?",
                (frontier_id,),
            ).fetchone()
        if row is None:
            return None
        return ParetoFrontier.model_validate_json(_row_str(row, "raw_json"))

    def list_frontiers(
        self,
        *,
        run_id: str | None = None,
        limit: int = 20,
    ) -> list[ParetoFrontier]:
        """List persisted frontiers newest-first."""

        with connect_database(self.database_path) as connection:
            if run_id is None:
                rows = connection.execute(
                    """
                    SELECT raw_json FROM pareto_frontiers
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT raw_json FROM pareto_frontiers
                    WHERE run_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (run_id, limit),
                ).fetchall()
        return [ParetoFrontier.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def list_selections_by_run(self, run_id: str) -> list[ParetoSelectionResult]:
        """List all Pareto selections for one run."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM pareto_selections
                WHERE run_id = ?
                ORDER BY created_at, frontier_id
                """,
                (run_id,),
            ).fetchall()
        return [ParetoSelectionResult.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def list_candidates(self, frontier_id: str) -> list[DecisionCandidate]:
        """List candidate rows for one frontier."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM pareto_candidates
                WHERE frontier_id = ?
                ORDER BY candidate_id
                """,
                (frontier_id,),
            ).fetchall()
        return [DecisionCandidate.model_validate_json(_row_str(row, "raw_json")) for row in rows]


def _datetime_to_text(value: object) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])
