from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from app.models import ExperimentRun


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


class MetricsService:
    """Aggregate quality, cost, latency, errors and stability by model."""

    def aggregate(self, runs: list[ExperimentRun]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, list[ExperimentRun]] = defaultdict(list)
        for run in runs:
            grouped[str(run.model_id)].append(run)
        result: dict[str, dict[str, Any]] = {}
        for model_id, model_runs in grouped.items():
            successful = [run for run in model_runs if run.status == "completed"]
            latencies = [run.latency_ms or 0.0 for run in successful]
            evaluation_scores = [
                evaluation.score
                for run in successful
                for evaluation in run.evaluations
                if evaluation.score is not None
            ]
            passes = [
                evaluation.passed
                for run in successful
                for evaluation in run.evaluations
                if evaluation.passed is not None
            ]
            costs = [run.total_cost for run in successful]
            result[model_id] = {
                "runs": len(model_runs),
                "successful_runs": len(successful),
                "quality": statistics.fmean(evaluation_scores) if evaluation_scores else 0.0,
                "pass_rate": sum(bool(item) for item in passes) / len(passes) if passes else 0.0,
                "mean_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
                "median_latency_ms": statistics.median(latencies) if latencies else 0.0,
                "p95_latency_ms": percentile(latencies, 0.95),
                "p99_latency_ms": percentile(latencies, 0.99),
                "total_cost": sum(costs),
                "mean_cost": statistics.fmean(costs) if costs else 0.0,
                "cost_per_pass": sum(costs) / sum(bool(item) for item in passes)
                if any(passes)
                else None,
                "error_rate": (len(model_runs) - len(successful)) / len(model_runs),
                "latency_stddev": statistics.pstdev(latencies) if len(latencies) > 1 else 0.0,
                "cost_stddev": statistics.pstdev(costs) if len(costs) > 1 else 0.0,
            }
        return result


metrics_service = MetricsService()
