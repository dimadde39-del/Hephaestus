"""Rich renderers for QUBO and Ising formulations."""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from hephaestus.qubo.schemas import (
    FormulationReport,
    IsingProblem,
    QuboComparisonResult,
    QuboProblem,
    QuboSolution,
)


def build_formulation_report_renderable(report: FormulationReport) -> Group:
    """Render a newly created formulation report."""

    problem = report.problem
    return Group(
        Panel(
            "\n".join(
                [
                    f"Problem id: {problem.id}",
                    f"Type: {problem.problem_type.value}",
                    f"Variables: {report.variable_count}",
                    f"Linear terms: {report.linear_term_count}",
                    f"Quadratic terms: {report.quadratic_term_count}",
                    f"Constraints: {report.constraint_count}",
                    report.summary,
                ]
            ),
            title="QUBO Formulation",
        ),
        _variable_table(problem),
        _constraint_table(problem),
        _notes_panel(report.notes),
    )


def build_qubo_problem_list_table(problems: Sequence[QuboProblem]) -> Table:
    """Render persisted QUBO problem summaries."""

    table = Table(title="QUBO Problems")
    table.add_column("ID", no_wrap=True)
    table.add_column("Run", no_wrap=True)
    table.add_column("Type")
    table.add_column("Variables", justify="right")
    table.add_column("Terms", justify="right")
    table.add_column("Constraints", justify="right")
    table.add_column("Source")
    table.add_column("Created")
    if not problems:
        table.add_row("none", "-", "-", "0", "0", "0", "-", "-")
        return table
    for problem in problems:
        table.add_row(
            problem.id,
            problem.run_id or "-",
            problem.problem_type.value,
            str(len(problem.variables)),
            str(len(problem.linear_terms) + len(problem.quadratic_terms)),
            str(len(problem.constraints)),
            problem.source_benchmark_id or problem.source_frontier_id or "-",
            problem.created_at.isoformat(timespec="seconds"),
        )
    return table


def build_qubo_problem_renderable(
    problem: QuboProblem,
    latest_solution: QuboSolution | None = None,
) -> Group:
    """Render one QUBO problem and optionally its latest solution."""

    renderables: list[RenderableType] = [
        Panel(
            "\n".join(
                [
                    f"Run: {problem.run_id or '-'}",
                    f"Type: {problem.problem_type.value}",
                    f"Source benchmark: {problem.source_benchmark_id or '-'}",
                    f"Source frontier: {problem.source_frontier_id or '-'}",
                    f"Constant offset: {problem.constant_offset:.6f}",
                    f"Objective: {problem.objective.description or 'minimize QUBO energy'}",
                ]
            ),
            title=f"QUBO Problem {problem.id}",
        ),
        _variable_table(problem),
        _term_table(problem),
        _constraint_table(problem),
    ]
    if latest_solution is not None:
        renderables.append(build_qubo_solution_renderable(latest_solution, problem))
    return Group(*renderables)


def build_qubo_solution_renderable(solution: QuboSolution, problem: QuboProblem) -> Group:
    """Render a QUBO solution."""

    selected_labels = _selected_labels(problem, solution)
    violation_text = "\n".join(solution.constraint_violations) or "none"
    return Group(
        Panel(
            "\n".join(
                [
                    f"Solver: {solution.solver_name}",
                    f"Objective value: {solution.objective_value:.6f}",
                    f"Feasible: {'yes' if solution.feasible else 'no'}",
                    "Selected: " + (", ".join(selected_labels) or "none"),
                    f"Iterations: {solution.iterations}",
                    "",
                    solution.explanation,
                    "",
                    f"Constraint violations: {violation_text}",
                ]
            ),
            title=f"QUBO Solution {solution.id}",
        )
    )


def build_ising_renderable(problem: IsingProblem) -> Group:
    """Render an Ising conversion summary."""

    table = Table(title="Ising Terms")
    table.add_column("Type")
    table.add_column("Variables")
    table.add_column("Coefficient", justify="right")
    for term in problem.linear_terms:
        table.add_row("linear", ", ".join(term.variable_ids), f"{term.coefficient:.6f}")
    for term in problem.quadratic_terms:
        table.add_row("quadratic", ", ".join(term.variable_ids), f"{term.coefficient:.6f}")
    if not problem.linear_terms and not problem.quadratic_terms:
        table.add_row("none", "-", "0")
    return Group(
        Panel(
            "\n".join(
                [
                    f"QUBO problem: {problem.qubo_problem_id}",
                    f"Variables: {len(problem.variables)}",
                    f"Linear terms: {len(problem.linear_terms)}",
                    f"Quadratic terms: {len(problem.quadratic_terms)}",
                    f"Constant offset: {problem.constant_offset:.6f}",
                    f"Convention: {problem.convention}",
                    problem.explanation,
                ]
            ),
            title=f"Ising Problem {problem.id}",
        ),
        table,
    )


def build_qubo_comparison_table(comparisons: Sequence[QuboComparisonResult]) -> Table:
    """Render QUBO versus baseline comparison rows."""

    table = Table(title="QUBO Comparison")
    table.add_column("Problem", no_wrap=True)
    table.add_column("Baseline", overflow="fold")
    table.add_column("QUBO", overflow="fold")
    table.add_column("Delta", justify="right")
    table.add_column("Feasible")
    table.add_column("Notes", overflow="fold")
    if not comparisons:
        table.add_row("none", "-", "-", "0.000", "-", "-")
        return table
    for comparison in comparisons:
        table.add_row(
            comparison.problem_type.value,
            comparison.baseline_selected,
            comparison.qubo_selected,
            f"{comparison.objective_difference:+.3f}",
            "yes" if comparison.feasible else "no",
            "; ".join(comparison.notes) or "-",
        )
    return table


def build_qubo_summary_panel(
    problems: Sequence[QuboProblem],
    latest_solutions: Sequence[QuboSolution | None],
) -> Panel:
    """Render compact QUBO metrics for explain --summary."""

    solutions = [solution for solution in latest_solutions if solution is not None]
    feasible = sum(1 for solution in solutions if solution.feasible)
    infeasible = sum(1 for solution in solutions if not solution.feasible)
    best = min((solution.objective_value for solution in solutions), default=None)
    return Panel(
        "\n".join(
            [
                f"QUBO problems count: {len(problems)}",
                f"Feasible solutions count: {feasible}",
                f"Infeasible solutions count: {infeasible}",
                f"Best objective value: {best:.6f}" if best is not None else "Best objective value: none",
            ]
        ),
        title="QUBO Summary",
    )


def build_qubo_explain_renderable(
    problems: Sequence[QuboProblem],
    latest_solutions: Sequence[QuboSolution | None],
) -> Group:
    """Render QUBO details for a run explanation."""

    table = Table(title="QUBO")
    table.add_column("Problem", no_wrap=True)
    table.add_column("Type", no_wrap=True)
    table.add_column("Variables", justify="right")
    table.add_column("Solver")
    table.add_column("Selected", overflow="fold")
    table.add_column("Feasible")
    table.add_column("Objective", justify="right")
    table.add_column("Why", overflow="fold")
    if not problems:
        table.add_row("none", "-", "0", "-", "-", "-", "-", "-")
        return Group(table)
    for problem, solution in zip(problems, latest_solutions, strict=True):
        if solution is None:
            table.add_row(problem.id, problem.problem_type.value, str(len(problem.variables)), "-", "-", "-", "-", "-")
            continue
        table.add_row(
            problem.id,
            problem.problem_type.value,
            str(len(problem.variables)),
            solution.solver_name,
            ", ".join(_selected_labels(problem, solution)) or "none",
            "yes" if solution.feasible else "no",
            f"{solution.objective_value:.3f}",
            _why_text(problem, solution),
        )
    return Group(table)


def _variable_table(problem: QuboProblem) -> Table:
    table = Table(title="QUBO Variables")
    table.add_column("Variable", no_wrap=True)
    table.add_column("Label", overflow="fold")
    table.add_column("Meaning", overflow="fold")
    table.add_column("Metadata", overflow="fold")
    for variable in problem.variables:
        table.add_row(
            variable.id,
            variable.label or "-",
            variable.description or "-",
            _metadata_preview(variable.metadata),
        )
    if not problem.variables:
        table.add_row("none", "-", "-", "-")
    return table


def _term_table(problem: QuboProblem) -> Table:
    table = Table(title="QUBO Objective Terms")
    table.add_column("Type")
    table.add_column("Variables")
    table.add_column("Coefficient", justify="right")
    table.add_column("Reason", overflow="fold")
    for term in problem.linear_terms:
        table.add_row("linear", ", ".join(term.variable_ids), f"{term.coefficient:.6f}", term.reason)
    for term in problem.quadratic_terms:
        table.add_row(
            "quadratic",
            ", ".join(term.variable_ids),
            f"{term.coefficient:.6f}",
            term.reason,
        )
    if not problem.linear_terms and not problem.quadratic_terms:
        table.add_row("none", "-", "0", "-")
    return table


def _constraint_table(problem: QuboProblem) -> Table:
    table = Table(title="QUBO Constraints")
    table.add_column("ID", no_wrap=True)
    table.add_column("Type")
    table.add_column("Penalty", justify="right")
    table.add_column("Description", overflow="fold")
    for constraint in problem.constraints:
        table.add_row(
            constraint.id,
            constraint.constraint_type.value,
            f"{constraint.penalty_weight:.3f}",
            constraint.description,
        )
    if not problem.constraints:
        table.add_row("none", "-", "0", "-")
    return table


def _notes_panel(notes: Sequence[str]) -> Panel:
    return Panel("\n".join(notes) if notes else "No formulation notes.", title="Notes")


def _selected_labels(problem: QuboProblem, solution: QuboSolution) -> list[str]:
    labels = {variable.id: variable.label or variable.id for variable in problem.variables}
    return [labels.get(variable_id, variable_id) for variable_id in solution.selected_variables]


def _why_text(problem: QuboProblem, solution: QuboSolution) -> str:
    if solution.constraint_violations:
        return "Violations: " + "; ".join(solution.constraint_violations)
    if problem.problem_type.value == "model_selection":
        rejected = [
            variable.label
            for variable in problem.variables
            if variable.id not in set(solution.selected_variables)
            and any("quality" in str(item).lower() for item in variable.metadata.get("violations", []))
        ]
        if rejected:
            return f"Lower-energy feasible model; quality penalty rejected {', '.join(rejected)}."
    return solution.explanation


def _metadata_preview(metadata: dict[str, object]) -> str:
    if not metadata:
        return "-"
    parts: list[str] = []
    for key in sorted(metadata)[:5]:
        value = metadata[key]
        if isinstance(value, float):
            parts.append(f"{key}={value:.3f}")
        elif isinstance(value, list):
            parts.append(f"{key}={len(value)} items")
        else:
            parts.append(f"{key}={value}")
    return "; ".join(parts)
