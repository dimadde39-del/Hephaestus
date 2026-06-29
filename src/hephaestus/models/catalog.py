"""Provider catalog metadata used for defaults and local cost estimates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPricing:
    provider_type: str
    model: str
    input_cost_per_million: float
    cached_input_cost_per_million: float | None
    output_cost_per_million: float
    source: str
    version: str


DEEPSEEK_V4_FLASH_PRICING = ProviderPricing(
    provider_type="deepseek",
    model="deepseek-v4-flash",
    input_cost_per_million=0.14,
    cached_input_cost_per_million=0.0028,
    output_cost_per_million=0.28,
    source="provider-catalog:deepseek",
    version="2026-06-29",
)


def pricing_for(provider_type: str, model: str) -> ProviderPricing | None:
    normalized_provider = provider_type.strip().lower()
    normalized_model = model.strip().lower()
    if normalized_provider == "deepseek" and normalized_model == "deepseek-v4-flash":
        return DEEPSEEK_V4_FLASH_PRICING
    return None
