from app.services.recommendation_service import RecommendationService
from app.services.regression_service import RegressionService


def test_recommendation_balances_multiple_objectives() -> None:
    metrics = {
        "quality_model": {
            "quality": 0.98,
            "mean_cost": 0.2,
            "mean_latency_ms": 900,
            "latency_stddev": 100,
            "error_rate": 0.02,
        },
        "balanced_model": {
            "quality": 0.94,
            "mean_cost": 0.02,
            "mean_latency_ms": 300,
            "latency_stddev": 20,
            "error_rate": 0.01,
        },
    }
    result = RecommendationService().recommend(
        metrics,
        {"quality": 0.35, "cost": 0.30, "latency": 0.20, "stability": 0.10, "error_rate": 0.05},
    )
    assert result["recommended_model_id"] == "balanced_model"
    assert result["highest_quality"] == "quality_model"
    assert result["fallback_model_id"] == "quality_model"


def test_recommendation_respects_minimum_thresholds() -> None:
    metrics = {
        "model": {
            "quality": 0.7,
            "mean_cost": 0.01,
            "mean_latency_ms": 100,
            "latency_stddev": 0,
            "error_rate": 0,
        }
    }
    result = RecommendationService().recommend(
        metrics,
        {"quality": 1},
        {"minimum_quality": 0.8},
    )
    assert result["recommended_model_id"] is None


def test_regression_reports_each_degraded_metric() -> None:
    result = RegressionService().compare(
        {"quality": 0.85, "cost": 1.2, "latency": 105, "error_rate": 0.03},
        {"quality": 0.95, "cost": 1.0, "latency": 100, "error_rate": 0.01},
        {"quality_drop": 3, "cost_increase": 10, "latency_increase": 15, "error_rate_increase": 2},
    )
    assert result["status"] == "critical"
    assert result["metric_changes"]["quality"]["regression"] is True
    assert result["metric_changes"]["cost"]["regression"] is True
    assert result["metric_changes"]["latency"]["regression"] is False
