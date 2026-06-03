import pytest

from hephaestus.models.base import ModelProfile
from hephaestus.optimize.model_router import ModelRouteRequest, ModelRoutingError, route_model


def test_router_rejects_too_cheap_low_quality_model() -> None:
    cheap = ModelProfile(
        provider="cheap",
        model="tiny",
        capabilities={"coding"},
        context_window=10_000,
        input_cost_per_million=0.01,
        output_cost_per_million=0.01,
        quality_scores={"coding": 0.55, "general": 0.55},
        supports_json=True,
    )
    strong = ModelProfile(
        provider="strong",
        model="capable",
        capabilities={"coding"},
        context_window=10_000,
        input_cost_per_million=0.2,
        output_cost_per_million=0.4,
        quality_scores={"coding": 0.9, "general": 0.9},
        supports_json=True,
    )

    route = route_model(
        ModelRouteRequest(
            required_capabilities={"coding"},
            input_tokens=1_000,
            output_tokens=500,
            quality_threshold=0.8,
            needs_json=True,
            profiles=[cheap, strong],
        )
    )

    assert route.profile.identifier == "strong/capable"
    assert any(rejected.identifier == "cheap/tiny" for rejected in route.rejected)


def test_router_errors_when_no_model_meets_threshold() -> None:
    weak = ModelProfile(
        provider="weak",
        model="only",
        capabilities={"analysis"},
        context_window=10_000,
        input_cost_per_million=0,
        output_cost_per_million=0,
        quality_scores={"analysis": 0.4},
    )

    with pytest.raises(ModelRoutingError):
        route_model(
            ModelRouteRequest(
                required_capabilities={"analysis"},
                input_tokens=100,
                output_tokens=50,
                quality_threshold=0.9,
                profiles=[weak],
            )
        )
