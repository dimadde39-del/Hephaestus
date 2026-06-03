from hephaestus.optimize.objective import count_dependency_violations
from hephaestus.optimize.task_scheduler import compare_schedulers
from hephaestus.spec.tasks import Task


def test_schedulers_respect_dependencies() -> None:
    tasks = [
        _task("deploy", dependencies=["test"], priority=10, expected_value=10),
        _task("inspect", priority=7, expected_value=7),
        _task("test", dependencies=["inspect"], priority=9, expected_value=9),
    ]

    comparison = compare_schedulers(tasks)

    greedy_ids = [task.id for task in comparison.greedy.order]
    annealed_ids = [task.id for task in comparison.annealed.order]
    assert greedy_ids.index("inspect") < greedy_ids.index("test") < greedy_ids.index("deploy")
    assert count_dependency_violations(comparison.greedy.order) == 0
    assert count_dependency_violations(comparison.annealed.order) == 0
    assert set(annealed_ids) == {"inspect", "test", "deploy"}


def test_annealing_compares_against_greedy() -> None:
    tasks = [
        _task("a", priority=3, expected_value=3),
        _task("b", dependencies=["a"], priority=9, expected_value=9),
        _task("c", dependencies=["b"], priority=8, expected_value=8),
    ]

    comparison = compare_schedulers(tasks)

    assert comparison.best_score >= comparison.greedy.score
    assert comparison.explanation.startswith("Greedy score")


def _task(
    task_id: str,
    *,
    dependencies: list[str] | None = None,
    priority: int,
    expected_value: float,
) -> Task:
    return Task(
        id=task_id,
        title=task_id,
        description=task_id,
        priority=priority,
        dependencies=dependencies or [],
        risk=0.1,
        expected_value=expected_value,
        uncertainty=0.1,
        required_capabilities={"planning"},
        estimated_input_tokens=100,
        estimated_output_tokens=50,
    )
