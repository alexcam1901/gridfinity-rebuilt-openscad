"""Per-model pricing used to turn measured usage into a $/photo figure.

LLM rates are USD per 1M tokens (input, output). Rekognition is a flat per-call
image price. Keep these in sync with the plan's cost table; they are estimates
for relative comparison, not billing.
"""
from __future__ import annotations

from dataclasses import dataclass

from .schema import Usage


@dataclass(frozen=True)
class TokenPricing:
    input_per_mtok: float
    output_per_mtok: float

    def cost(self, usage: Usage) -> float:
        return (
            usage.input_tokens * self.input_per_mtok
            + usage.output_tokens * self.output_per_mtok
        ) / 1_000_000


@dataclass(frozen=True)
class PerCallPricing:
    usd_per_call: float

    def cost(self, usage: Usage) -> float:
        return usage.api_calls * self.usd_per_call


# Model name -> pricing. Matches the IDs the adapters report.
PRICING: dict[str, TokenPricing | PerCallPricing] = {
    "claude-haiku-4-5": TokenPricing(1.0, 5.0),
    "claude-sonnet-4-6": TokenPricing(3.0, 15.0),
    "nova-2-lite": TokenPricing(0.30, 2.50),
    # Rekognition: ~$0.001 per image per API call (DetectLabels + DetectText = 2).
    "rekognition": PerCallPricing(0.001),
    "stub": PerCallPricing(0.0),
}


def cost_for(model_name: str, usage: Usage) -> float | None:
    p = PRICING.get(model_name)
    return p.cost(usage) if p else None
