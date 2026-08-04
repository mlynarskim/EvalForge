from __future__ import annotations

from typing import Any


def _benefit_scores(values: dict[str, float], higher_is_better: bool) -> dict[str, float]:
    if not values:
        return {}
    minimum, maximum = min(values.values()), max(values.values())
    if maximum == minimum:
        return {key: 1.0 for key in values}
    normalized = {key: (value - minimum) / (maximum - minimum) for key, value in values.items()}
    return (
        normalized if higher_is_better else {key: 1.0 - value for key, value in normalized.items()}
    )


class RecommendationService:
    """Rank models using user controlled multi objective weights and thresholds."""

    def recommend(
        self,
        metrics: dict[str, dict[str, Any]],
        weights: dict[str, float],
        thresholds: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        thresholds = thresholds or {}
        eligible = {
            key: value
            for key, value in metrics.items()
            if value.get("quality", 0) >= thresholds.get("minimum_quality", 0)
            and value.get("error_rate", 1) <= thresholds.get("maximum_error_rate", 1)
            and value.get("mean_latency_ms", 0)
            <= thresholds.get("maximum_latency_ms", float("inf"))
        }
        if not eligible:
            return {"recommended_model_id": None, "reason": "No model meets the minimum thresholds"}
        columns = {
            "quality": _benefit_scores(
                {key: val["quality"] for key, val in eligible.items()}, True
            ),
            "cost": _benefit_scores(
                {key: val["mean_cost"] for key, val in eligible.items()}, False
            ),
            "latency": _benefit_scores(
                {key: val["mean_latency_ms"] for key, val in eligible.items()}, False
            ),
            "stability": _benefit_scores(
                {key: val["latency_stddev"] for key, val in eligible.items()}, False
            ),
            "error_rate": _benefit_scores(
                {key: val["error_rate"] for key, val in eligible.items()}, False
            ),
        }
        scores = {
            model_id: sum(
                weights.get(metric, 0) * values[model_id] for metric, values in columns.items()
            )
            for model_id in eligible
        }
        ranking = sorted(scores, key=lambda model_id: scores[model_id], reverse=True)
        winner = ranking[0]
        fallback = ranking[1] if len(ranking) > 1 else None
        return {
            "recommended_model_id": winner,
            "fallback_model_id": fallback,
            "scores": scores,
            "ranking": ranking,
            "highest_quality": max(eligible, key=lambda key: eligible[key]["quality"]),
            "lowest_cost": min(eligible, key=lambda key: eligible[key]["mean_cost"]),
            "lowest_latency": min(eligible, key=lambda key: eligible[key]["mean_latency_ms"]),
            "reason": "Best weighted balance of quality, cost, latency, stability and errors",
        }


recommendation_service = RecommendationService()
