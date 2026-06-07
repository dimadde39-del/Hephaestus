"""Builders that convert optimizer outcomes into decision traces."""

from __future__ import annotations

from collections.abc import Sequence

from hephaestus.core.config import RiskLevel
from hephaestus.decision.schemas import (
    BudgetDecision as BudgetTraceDecision,
)
from hephaestus.decision.schemas import (
    ContextSelectionDecision,
    DecisionAlternative,
    DecisionMetric,
    ModelRoutingDecision,
    OptimizationDecision,
    TaskSelectionDecision,
    metric,
)
from hephaestus.decision.schemas import (
    SafetyDecision as SafetyTraceDecision,
)
from hephaestus.models.base import ModelProfile
from hephaestus.optimize.context_packer import (
    ContextCandidate,
    ContextPackResult,
    ExcludedContext,
)
from hephaestus.optimize.greedy import SchedulerResult
from hephaestus.optimize.model_router import ModelRoute, ModelRouteRequest
from hephaestus.optimize.task_scheduler import SchedulerComparison
from hephaestus.optimize.token_firewall import (
    BudgetDecision as BudgetEvaluation,
)
from hephaestus.optimize.token_firewall import (
    TokenBudget,
)
from hephaestus.safety.policy import SafetyDecision as PolicySafetyDecision
from hephaestus.spec.tasks import Task


class DecisionTraceBuilder:
    """Create rich decision traces for one run without scattered model construction."""

    def __init__(
        self,
        run_id: str,
        *,
        phase: str = "runtime",
        tags: Sequence[str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.phase = phase
        self.tags = list(tags or [])

    def task_selection(
        self,
        comparison: SchedulerComparison,
        *,
        parent_id: str | None = None,
    ) -> TaskSelectionDecision:
        """Explain the selected task order from scheduler comparison output."""

        selected_scheduler = _selected_scheduler_name(comparison)
        selected_order = _order_text(comparison.best_order)
        alternatives = [
            _scheduler_alternative("greedy", comparison.greedy, selected_scheduler),
            _scheduler_alternative("annealing", comparison.annealed, selected_scheduler),
        ]
        alternatives = [alternative for alternative in alternatives if alternative is not None]
        return TaskSelectionDecision(
            run_id=self.run_id,
            phase=self.phase,
            selected_option=selected_order or "none",
            alternatives=alternatives,
            rationale=(
                f"Selected {selected_scheduler} task order because it produced the highest "
                "objective score while accounting for dependencies, priority, value, and risk."
            ),
            metrics=[
                metric("greedy_score", comparison.greedy.score, higher_is_better=True),
                metric("annealing_score", comparison.annealed.score, higher_is_better=True),
                metric(
                    "score_delta",
                    comparison.annealed.score - comparison.greedy.score,
                    description="Annealing score minus greedy score.",
                    higher_is_better=True,
                ),
                metric("selected_task_count", len(comparison.best_order)),
                metric(
                    "greedy_dependency_violations",
                    comparison.greedy.breakdown.dependency_violations,
                    higher_is_better=False,
                ),
                metric(
                    "annealing_dependency_violations",
                    comparison.annealed.breakdown.dependency_violations,
                    higher_is_better=False,
                ),
            ],
            objective_score=comparison.best_score,
            confidence=0.84,
            constraints_considered=[
                "dependency order",
                "priority",
                "expected value",
                "risk",
                "uncertainty",
            ],
            tags=[*self.tags, "scheduler", "task-order"],
            caused_by=["task_graph", "objective_weights"],
            will_affect=["execution_order", "model_routing", "approval_sequence"],
            learning_hooks=[
                "task_order_outcome",
                "dependency_failure",
                "scheduler_performance",
            ],
            parent_id=parent_id,
        )

    def optimization(
        self,
        comparison: SchedulerComparison,
        *,
        parent_id: str | None = None,
    ) -> OptimizationDecision:
        """Explain why one scheduler result won the optimization comparison."""

        selected_scheduler = _selected_scheduler_name(comparison)
        score_delta = comparison.annealed.score - comparison.greedy.score
        alternatives = [
            _scheduler_score_alternative("greedy", comparison.greedy, selected_scheduler),
            _scheduler_score_alternative("annealing", comparison.annealed, selected_scheduler),
        ]
        alternatives = [alternative for alternative in alternatives if alternative is not None]
        return OptimizationDecision(
            run_id=self.run_id,
            phase=self.phase,
            selected_option=selected_scheduler,
            alternatives=alternatives,
            rationale=(
                f"Selected {selected_scheduler}; annealing minus greedy score was "
                f"{score_delta:+.2f}."
            ),
            metrics=[
                metric("greedy_score", comparison.greedy.score, higher_is_better=True),
                metric("annealing_score", comparison.annealed.score, higher_is_better=True),
                metric("score_delta", score_delta, higher_is_better=True),
                metric("best_score", comparison.best_score, higher_is_better=True),
            ],
            objective_score=comparison.best_score,
            confidence=0.82,
            constraints_considered=[
                "objective utility",
                "dependency violation penalty",
                "scheduler score comparison",
            ],
            tags=[*self.tags, "optimizer"],
            caused_by=["objective_weights", "task_graph"],
            will_affect=["task_selection"],
            learning_hooks=[
                "optimizer_score_vs_outcome",
                "pareto_debugging",
                "qubo_policy_future",
            ],
            parent_id=parent_id,
        )

    def model_routing(
        self,
        request: ModelRouteRequest,
        route: ModelRoute,
        *,
        task_id: str | None = None,
        parent_id: str | None = None,
    ) -> ModelRoutingDecision:
        """Explain a successful model routing decision."""

        rationale = route.explanation
        if task_id is not None:
            rationale = f"Task {task_id}: {rationale}"
        return ModelRoutingDecision(
            run_id=self.run_id,
            phase=self.phase,
            selected_option=route.profile.identifier,
            alternatives=_model_alternatives(request, selected=route.profile, route=route),
            rationale=rationale,
            metrics=[
                metric("input_tokens", request.input_tokens, unit="tokens"),
                metric("output_tokens", request.output_tokens, unit="tokens"),
                metric("quality_threshold", request.quality_threshold),
                metric("selected_quality", route.quality, higher_is_better=True),
                metric("estimated_cost", route.estimated_cost, unit="USD", higher_is_better=False),
                metric("candidate_count", len(request.profiles)),
                metric("rejected_count", len(route.rejected)),
                metric("needs_tools", request.needs_tools),
                metric("needs_json", request.needs_json),
            ],
            objective_score=route.quality,
            confidence=0.86,
            constraints_considered=_model_constraints(request),
            tags=[*self.tags, "model-routing", *(["task"] if task_id else [])],
            caused_by=_compact(["task:" + task_id if task_id else "", "model_profiles"]),
            will_affect=["model_call_cost", "expected_quality", "privacy_posture"],
            learning_hooks=[
                "model_quality_outcome",
                "model_cost_actual",
                "model_rejection_accuracy",
            ],
            parent_id=parent_id,
        )

    def model_routing_error(
        self,
        request: ModelRouteRequest,
        error: Exception,
        *,
        task_id: str | None = None,
        parent_id: str | None = None,
    ) -> ModelRoutingDecision:
        """Explain a failed model routing decision."""

        rationale = str(error)
        if task_id is not None:
            rationale = f"Task {task_id}: {rationale}"
        return ModelRoutingDecision(
            run_id=self.run_id,
            phase=self.phase,
            selected_option="unrouted",
            alternatives=_model_error_alternatives(request, str(error)),
            rationale=rationale,
            metrics=[
                metric("input_tokens", request.input_tokens, unit="tokens"),
                metric("output_tokens", request.output_tokens, unit="tokens"),
                metric("quality_threshold", request.quality_threshold),
                metric("candidate_count", len(request.profiles)),
                metric("rejected_count", len(request.profiles)),
                metric("needs_tools", request.needs_tools),
                metric("needs_json", request.needs_json),
            ],
            objective_score=0.0,
            confidence=0.66,
            constraints_considered=_model_constraints(request),
            tags=[*self.tags, "model-routing", "unrouted"],
            caused_by=_compact(["task:" + task_id if task_id else "", "model_profiles"]),
            will_affect=["manual_intervention", "task_delay"],
            learning_hooks=[
                "routing_failure",
                "quality_threshold_policy",
                "model_catalog_gap",
            ],
            parent_id=parent_id,
        )

    def context_selection(
        self,
        candidates: Sequence[ContextCandidate],
        result: ContextPackResult,
        token_budget: int,
        *,
        parent_id: str | None = None,
    ) -> ContextSelectionDecision:
        """Explain why context items were included or excluded."""

        tokens_before = sum(item.token_cost for item in candidates)
        token_savings = max(0, tokens_before - result.used_tokens)
        return ContextSelectionDecision(
            run_id=self.run_id,
            phase=self.phase,
            selected_option=", ".join(item.id for item in result.selected) or "none",
            alternatives=[
                _context_alternative(item, candidates) for item in result.excluded
            ],
            rationale=result.explanation,
            metrics=[
                metric("candidate_count", len(candidates)),
                metric("selected_count", len(result.selected)),
                metric("excluded_count", len(result.excluded)),
                metric("tokens_before", tokens_before, unit="tokens"),
                metric("tokens_after", result.used_tokens, unit="tokens"),
                metric("token_budget", token_budget, unit="tokens"),
                metric("token_savings", token_savings, unit="tokens", higher_is_better=True),
                metric("objective_score", result.score, higher_is_better=True),
            ],
            objective_score=result.score,
            confidence=0.81,
            constraints_considered=[
                "token budget",
                "critical context preservation",
                "relevance",
                "importance",
                "value per token",
            ],
            tags=[*self.tags, "context"],
            caused_by=["context_candidates", "token_budget"],
            will_affect=["prompt_content", "model_input_tokens", "answer_quality"],
            learning_hooks=[
                "context_item_outcome",
                "token_savings_quality_tradeoff",
                "critical_context_policy",
            ],
            parent_id=parent_id,
        )

    def budget(
        self,
        decision: BudgetEvaluation,
        budget: TokenBudget,
        *,
        parent_id: str | None = None,
    ) -> BudgetTraceDecision:
        """Explain token, cost, and quality budget evaluation."""

        token_savings = _token_savings(decision, budget)
        selected = "approved" if decision.approved else "blocked"
        if not decision.approved and token_savings > 0:
            selected = "intervened"
        return BudgetTraceDecision(
            run_id=self.run_id,
            phase=self.phase,
            selected_option=selected,
            alternatives=_budget_alternatives(decision),
            rationale=decision.explanation,
            metrics=[
                metric("input_tokens", decision.input_tokens, unit="tokens"),
                metric("output_tokens", decision.output_tokens, unit="tokens"),
                metric("max_input_tokens", budget.max_input_tokens, unit="tokens"),
                metric("max_output_tokens", budget.max_output_tokens, unit="tokens"),
                metric("estimated_cost", decision.estimated_cost, unit="USD"),
                metric("max_cost", budget.max_cost, unit="USD"),
                metric("quality_threshold", budget.quality_threshold),
                metric("within_token_budget", decision.within_token_budget),
                metric("within_cost_budget", decision.within_cost_budget),
                metric("meets_quality_threshold", decision.meets_quality_threshold),
                metric("savings_vs_baseline", decision.savings_vs_baseline, unit="USD"),
                metric("token_savings", token_savings, unit="tokens"),
            ],
            objective_score=1.0 if decision.approved else 0.0,
            confidence=0.9,
            constraints_considered=[
                "input token budget",
                "output token budget",
                "cost budget",
                "quality threshold",
            ],
            tags=[*self.tags, "budget", "token-firewall"],
            caused_by=["model_route", "token_budget"],
            will_affect=["model_call_allowed", "compression_or_blocking"],
            learning_hooks=[
                "budget_intervention_outcome",
                "quality_preservation",
                "cost_policy_update",
            ],
            parent_id=parent_id,
        )

    def safety_approval(
        self,
        *,
        action: str,
        reason: str,
        risk_level: RiskLevel,
        parent_id: str | None = None,
    ) -> SafetyTraceDecision:
        """Explain an approval-required action recorded by the approval system."""

        return SafetyTraceDecision(
            run_id=self.run_id,
            phase=self.phase,
            selected_option=f"approval_required: {action}",
            alternatives=[
                DecisionAlternative(
                    option_id="allow_without_approval",
                    rejection_reason="human approval required for this risk profile",
                    violated_constraints=["approval policy", "side-effect risk"],
                    risk=_risk_value(risk_level),
                )
            ],
            rationale=reason,
            metrics=[
                metric("approval_required", True),
                metric("risk_level", risk_level.value),
                metric("action", action),
            ],
            objective_score=0.0,
            confidence=0.88,
            constraints_considered=[
                "human approval for risky action",
                "side-effect risk",
                "auditability",
            ],
            tags=[*self.tags, "safety", "approval"],
            caused_by=["safety_policy", "task_risk"],
            will_affect=["execution_gate", "approval_queue"],
            learning_hooks=[
                "approval_outcome",
                "risk_policy_precision",
                "human_override_pattern",
            ],
            parent_id=parent_id,
        )

    def safety_policy(
        self,
        *,
        action: str,
        decision: PolicySafetyDecision,
        parent_id: str | None = None,
    ) -> SafetyTraceDecision:
        """Explain a SafetyPolicy allow/block/approval decision."""

        selected = "allowed"
        if decision.requires_approval:
            selected = "approval_required"
        elif not decision.allowed:
            selected = "blocked"
        return SafetyTraceDecision(
            run_id=self.run_id,
            phase=self.phase,
            selected_option=f"{selected}: {action}",
            alternatives=[
                DecisionAlternative(
                    option_id=f"policy_reason_{index}",
                    rejection_reason=reason,
                    violated_constraints=_constraints_for_reason(reason),
                    risk=_risk_value(decision.risk_level),
                )
                for index, reason in enumerate(decision.reasons, start=1)
            ],
            rationale=", ".join(decision.reasons) or "Action satisfied safety policy.",
            metrics=[
                metric("allowed", decision.allowed),
                metric("approval_required", decision.requires_approval),
                metric("risk_level", decision.risk_level.value),
                metric("action", action),
            ],
            objective_score=1.0 if decision.allowed else 0.0,
            confidence=0.88,
            constraints_considered=[
                "dangerous command patterns",
                "tool side effects",
                "approval requirements",
            ],
            tags=[*self.tags, "safety", "policy"],
            caused_by=["safety_policy", "action_request"],
            will_affect=["tool_execution", "approval_queue"],
            learning_hooks=[
                "safety_policy_outcome",
                "false_positive_review",
                "failure_memory_link",
            ],
            parent_id=parent_id,
        )


def build_task_selection_decision(
    run_id: str,
    comparison: SchedulerComparison,
    *,
    parent_id: str | None = None,
) -> TaskSelectionDecision:
    """Explain the selected task order from scheduler comparison output."""

    return DecisionTraceBuilder(run_id).task_selection(comparison, parent_id=parent_id)


def build_optimization_decision(
    run_id: str,
    comparison: SchedulerComparison,
    *,
    parent_id: str | None = None,
) -> OptimizationDecision:
    """Explain why one scheduler result won the optimization comparison."""

    return DecisionTraceBuilder(run_id).optimization(comparison, parent_id=parent_id)


def build_model_routing_decision(
    run_id: str,
    request: ModelRouteRequest,
    route: ModelRoute,
    *,
    task_id: str | None = None,
    parent_id: str | None = None,
) -> ModelRoutingDecision:
    """Explain a successful model routing decision."""

    return DecisionTraceBuilder(run_id).model_routing(
        request,
        route,
        task_id=task_id,
        parent_id=parent_id,
    )


def build_model_routing_error_decision(
    run_id: str,
    request: ModelRouteRequest,
    error: Exception,
    *,
    task_id: str | None = None,
    parent_id: str | None = None,
) -> ModelRoutingDecision:
    """Explain a failed model routing decision."""

    return DecisionTraceBuilder(run_id).model_routing_error(
        request,
        error,
        task_id=task_id,
        parent_id=parent_id,
    )


def build_context_selection_decision(
    run_id: str,
    candidates: Sequence[ContextCandidate],
    result: ContextPackResult,
    token_budget: int,
    *,
    parent_id: str | None = None,
) -> ContextSelectionDecision:
    """Explain why context items were included or excluded."""

    return DecisionTraceBuilder(run_id).context_selection(
        candidates,
        result,
        token_budget,
        parent_id=parent_id,
    )


def build_budget_decision(
    run_id: str,
    decision: BudgetEvaluation,
    budget: TokenBudget,
    *,
    parent_id: str | None = None,
) -> BudgetTraceDecision:
    """Explain token, cost, and quality budget evaluation."""

    return DecisionTraceBuilder(run_id).budget(decision, budget, parent_id=parent_id)


def build_safety_approval_decision(
    run_id: str,
    *,
    action: str,
    reason: str,
    risk_level: RiskLevel,
    parent_id: str | None = None,
) -> SafetyTraceDecision:
    """Explain an approval-required action recorded by the approval system."""

    return DecisionTraceBuilder(run_id).safety_approval(
        action=action,
        reason=reason,
        risk_level=risk_level,
        parent_id=parent_id,
    )


def build_safety_policy_decision(
    run_id: str,
    *,
    action: str,
    decision: PolicySafetyDecision,
    parent_id: str | None = None,
) -> SafetyTraceDecision:
    """Explain a SafetyPolicy allow/block/approval decision."""

    return DecisionTraceBuilder(run_id).safety_policy(
        action=action,
        decision=decision,
        parent_id=parent_id,
    )


def _selected_scheduler_name(comparison: SchedulerComparison) -> str:
    return "annealing" if comparison.annealed.score >= comparison.greedy.score else "greedy"


def _order_text(tasks: Sequence[Task]) -> str:
    return " -> ".join(task.id for task in tasks)


def _scheduler_alternative(
    scheduler_name: str,
    result: SchedulerResult,
    selected_scheduler: str,
) -> DecisionAlternative | None:
    if scheduler_name == selected_scheduler:
        return None
    order = _order_text(result.order)
    dependency_violations = result.breakdown.dependency_violations
    return DecisionAlternative(
        option_id=scheduler_name,
        option_name=order or "none",
        score=result.score,
        rejection_reason="lower objective score than selected scheduler",
        violated_constraints=["scheduler score comparison"],
        metrics=[
            metric("order", order),
            metric("objective_score", result.score, higher_is_better=True),
            metric("dependency_violations", dependency_violations, higher_is_better=False),
        ],
        risk=float(dependency_violations),
    )


def _scheduler_score_alternative(
    scheduler_name: str,
    result: SchedulerResult,
    selected_scheduler: str,
) -> DecisionAlternative | None:
    if scheduler_name == selected_scheduler:
        return None
    dependency_violations = result.breakdown.dependency_violations
    return DecisionAlternative(
        option_id=scheduler_name,
        score=result.score,
        rejection_reason="lower objective score after dependency and risk penalties",
        violated_constraints=["objective utility", "dependency violation penalty"],
        metrics=[
            metric("objective_score", result.score, higher_is_better=True),
            metric("dependency_violations", dependency_violations, higher_is_better=False),
            metric("order", _order_text(result.order)),
        ],
        risk=float(dependency_violations),
    )


def _model_alternatives(
    request: ModelRouteRequest,
    *,
    selected: ModelProfile,
    route: ModelRoute,
) -> list[DecisionAlternative]:
    rejected = {item.identifier: item.reason for item in route.rejected}
    alternatives: list[DecisionAlternative] = []
    for profile in request.profiles:
        if profile.identifier == selected.identifier:
            continue
        reason = rejected.get(profile.identifier, "higher cost than selected valid model")
        alternatives.append(_model_alternative(profile, request, reason))
    return alternatives


def _model_error_alternatives(
    request: ModelRouteRequest,
    message: str,
) -> list[DecisionAlternative]:
    rejected = _parse_rejection_map(message)
    alternatives: list[DecisionAlternative] = []
    for profile in request.profiles:
        reason = rejected.get(profile.identifier, "no route satisfied all constraints")
        alternatives.append(_model_alternative(profile, request, reason))
    if alternatives:
        return alternatives
    return [
        DecisionAlternative(
            option_id="all",
            rejection_reason=message,
            violated_constraints=_constraints_for_reason(message),
        )
    ]


def _model_alternative(
    profile: ModelProfile,
    request: ModelRouteRequest,
    reason: str,
) -> DecisionAlternative:
    quality = profile.quality_for(request.required_capabilities)
    cost = profile.estimated_cost(request.input_tokens, request.output_tokens)
    return DecisionAlternative(
        option_id=profile.identifier,
        score=quality,
        rejection_reason=reason,
        violated_constraints=_constraints_for_reason(reason),
        metrics=[
            metric("candidate_quality", quality, higher_is_better=True),
            metric("required_quality", request.quality_threshold),
            metric("estimated_cost", cost, unit="USD", higher_is_better=False),
            metric("context_window", profile.context_window, unit="tokens"),
            metric("supports_tools", profile.supports_tools),
            metric("supports_json", profile.supports_json),
        ],
        would_have_cost=cost,
        expected_quality=quality,
        risk=max(0.0, 1.0 - quality),
    )


def _context_alternative(
    excluded: ExcludedContext,
    candidates: Sequence[ContextCandidate],
) -> DecisionAlternative:
    candidate = next((item for item in candidates if item.id == excluded.id), None)
    metrics: list[DecisionMetric] = []
    expected_quality: float | None = None
    would_have_cost: float | None = None
    risk: float | None = None
    if candidate is not None:
        value = _context_value(candidate)
        expected_quality = min(1.0, value / 4.5)
        would_have_cost = float(candidate.token_cost)
        risk = 0.25 if candidate.critical else max(0.0, 1.0 - expected_quality)
        metrics = [
            metric("token_cost", candidate.token_cost, unit="tokens", higher_is_better=False),
            metric("relevance", candidate.relevance, higher_is_better=True),
            metric("importance", candidate.importance, higher_is_better=True),
            metric("critical", candidate.critical),
            metric("context_value", value, higher_is_better=True),
        ]
    return DecisionAlternative(
        option_id=excluded.id,
        rejection_reason=excluded.reason,
        violated_constraints=_constraints_for_reason(excluded.reason),
        metrics=metrics,
        would_have_cost=would_have_cost,
        expected_quality=expected_quality,
        risk=risk,
    )


def _budget_alternatives(decision: BudgetEvaluation) -> list[DecisionAlternative]:
    alternatives: list[DecisionAlternative] = []
    for reason in _budget_rejection_reasons(decision):
        alternatives.append(
            DecisionAlternative(
                option_id=reason.replace(" ", "_"),
                rejection_reason=reason,
                violated_constraints=_constraints_for_reason(reason),
                metrics=[
                    metric("input_tokens", decision.input_tokens),
                    metric("output_tokens", decision.output_tokens),
                    metric("estimated_cost", decision.estimated_cost, unit="USD"),
                ],
            )
        )
    return alternatives


def _model_constraints(request: ModelRouteRequest) -> list[str]:
    return [
        f"required capabilities: {', '.join(sorted(request.required_capabilities)) or 'none'}",
        f"quality >= {request.quality_threshold:.2f}",
        f"privacy >= {request.privacy_level.value}",
        f"context tokens <= model context window ({request.input_tokens + request.output_tokens})",
        f"tools required: {request.needs_tools}",
        f"JSON required: {request.needs_json}",
    ]


def _parse_rejection_map(message: str) -> dict[str, str]:
    marker = "Rejections:"
    if marker not in message:
        return {}
    rejected = message.split(marker, 1)[1]
    parsed: dict[str, str] = {}
    for part in rejected.split(";"):
        if ":" not in part:
            continue
        identifier, reason = part.split(":", 1)
        parsed[identifier.strip()] = reason.strip()
    return parsed


def _budget_rejection_reasons(decision: BudgetEvaluation) -> list[str]:
    rejected: list[str] = []
    if not decision.within_token_budget:
        rejected.append("token budget exceeded")
    if not decision.within_cost_budget:
        rejected.append("cost budget exceeded")
    if not decision.meets_quality_threshold:
        rejected.append("quality threshold missed")
    return rejected


def _token_savings(decision: BudgetEvaluation, budget: TokenBudget) -> int:
    input_overage = max(0, decision.input_tokens - budget.max_input_tokens)
    output_overage = max(0, decision.output_tokens - budget.max_output_tokens)
    return input_overage + output_overage


def _context_value(item: ContextCandidate) -> float:
    return item.relevance * 2.0 + item.importance * 1.5 + (1.0 if item.critical else 0.0)


def _constraints_for_reason(reason: str) -> list[str]:
    lowered = reason.lower()
    constraints: list[str] = []
    if "quality" in lowered or "threshold" in lowered:
        constraints.append("quality threshold")
    if "capabilit" in lowered:
        constraints.append("required capabilities")
    if "context" in lowered or "token" in lowered:
        constraints.append("token budget")
    if "cost" in lowered:
        constraints.append("cost budget")
    if "tool" in lowered:
        constraints.append("tool support")
    if "json" in lowered:
        constraints.append("JSON output")
    if "privacy" in lowered:
        constraints.append("privacy policy")
    if "approval" in lowered:
        constraints.append("approval policy")
    if "side-effect" in lowered or "risk" in lowered:
        constraints.append("risk policy")
    return constraints or ["objective comparison"]


def _risk_value(risk_level: RiskLevel) -> float:
    return {
        RiskLevel.LOW: 0.1,
        RiskLevel.MEDIUM: 0.35,
        RiskLevel.HIGH: 0.7,
        RiskLevel.CRITICAL: 1.0,
    }[risk_level]


def _compact(values: Sequence[str]) -> list[str]:
    return [value for value in values if value]
