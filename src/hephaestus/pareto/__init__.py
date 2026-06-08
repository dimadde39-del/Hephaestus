"""Pareto decision frontier tools."""

from hephaestus.pareto.frontier import (
    compute_frontier,
    dominance_comparisons,
    is_dominated,
    rank_frontier,
)
from hephaestus.pareto.repository import ParetoRepository
from hephaestus.pareto.schemas import (
    CandidateType,
    DecisionCandidate,
    ObjectiveDimension,
    ObjectiveDirection,
    ObjectiveVector,
    ParetoComparison,
    ParetoFrontier,
    ParetoSelectionResult,
    PreferenceProfile,
    TradeoffExplanation,
)
from hephaestus.pareto.scorer import (
    generate_context_packing_candidates,
    generate_model_routing_candidates,
    generate_scheduler_candidates,
)
from hephaestus.pareto.selector import (
    builtin_preference_profiles,
    get_preference_profile,
    select_candidate,
)

__all__ = [
    "CandidateType",
    "DecisionCandidate",
    "ObjectiveDimension",
    "ObjectiveDirection",
    "ObjectiveVector",
    "ParetoComparison",
    "ParetoFrontier",
    "ParetoRepository",
    "ParetoSelectionResult",
    "PreferenceProfile",
    "TradeoffExplanation",
    "builtin_preference_profiles",
    "compute_frontier",
    "dominance_comparisons",
    "generate_context_packing_candidates",
    "generate_model_routing_candidates",
    "generate_scheduler_candidates",
    "get_preference_profile",
    "is_dominated",
    "rank_frontier",
    "select_candidate",
]
