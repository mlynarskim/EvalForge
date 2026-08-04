from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, settings
from app.providers.base import TokenUsage


@dataclass(slots=True)
class CostBreakdown:
    input_cost: float
    output_cost: float
    total_cost: float
    currency: str


class PricingService:
    """Calculate immutable run costs and convert currencies using configured rates."""

    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    def convert(self, amount: float, source: str, target: str) -> float:
        if source == target:
            return amount
        to_pln = {"PLN": 1.0, "USD": self.config.usd_to_pln, "EUR": self.config.eur_to_pln}
        if source not in to_pln or target not in to_pln:
            raise ValueError(f"Unsupported currency conversion: {source} to {target}")
        return amount * to_pln[source] / to_pln[target]

    def calculate(
        self, usage: TokenUsage, pricing: dict[str, float | str | None], target_currency: str
    ) -> CostBreakdown:
        input_price = float(pricing.get("input_price_per_million") or 0)
        output_price = float(pricing.get("output_price_per_million") or 0)
        cached_price = float(pricing.get("cached_input_price_per_million") or input_price)
        source_currency = str(pricing.get("currency") or "USD")
        regular_tokens = max(usage.input_tokens - usage.cached_tokens, 0)
        input_source = (regular_tokens * input_price + usage.cached_tokens * cached_price) / 1e6
        output_source = usage.output_tokens * output_price / 1e6
        input_cost = self.convert(input_source, source_currency, target_currency)
        output_cost = self.convert(output_source, source_currency, target_currency)
        return CostBreakdown(input_cost, output_cost, input_cost + output_cost, target_currency)


pricing_service = PricingService()
