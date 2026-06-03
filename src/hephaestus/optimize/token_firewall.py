"""Token and cost budget controls."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hephaestus.models.base import ModelProfile


class TokenBudget(BaseModel):
    max_input_tokens: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    max_cost: float = Field(ge=0)
    quality_threshold: float = Field(ge=0, le=1)


class BudgetDecision(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    within_token_budget: bool
    within_cost_budget: bool
    meets_quality_threshold: bool
    savings_vs_baseline: float | None = None
    explanation: str

    @property
    def approved(self) -> bool:
        return self.within_token_budget and self.within_cost_budget and self.meets_quality_threshold


def evaluate_budget(
    *,
    input_tokens: int,
    output_tokens: int,
    selected_model: ModelProfile,
    selected_quality: float,
    budget: TokenBudget,
    baseline_model: ModelProfile | None = None,
) -> BudgetDecision:
    """Evaluate whether a route preserves quality while staying inside budget."""

    estimated_cost = selected_model.estimated_cost(input_tokens, output_tokens)
    within_token_budget = (
        input_tokens <= budget.max_input_tokens and output_tokens <= budget.max_output_tokens
    )
    within_cost_budget = estimated_cost <= budget.max_cost
    meets_quality = selected_quality >= budget.quality_threshold
    savings: float | None = None
    savings_text = "No baseline model supplied for savings comparison."
    if baseline_model is not None:
        baseline_cost = baseline_model.estimated_cost(input_tokens, output_tokens)
        savings = max(0.0, baseline_cost - estimated_cost)
        savings_text = f"Estimated savings versus {baseline_model.identifier}: ${savings:.6f}."

    explanation = (
        f"{selected_model.identifier} uses {input_tokens}+{output_tokens} tokens at "
        f"about ${estimated_cost:.6f}. Quality {selected_quality:.2f} "
        f"{'meets' if meets_quality else 'misses'} threshold {budget.quality_threshold:.2f}. "
        f"{savings_text}"
    )
    return BudgetDecision(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
        within_token_budget=within_token_budget,
        within_cost_budget=within_cost_budget,
        meets_quality_threshold=meets_quality,
        savings_vs_baseline=savings,
        explanation=explanation,
    )
