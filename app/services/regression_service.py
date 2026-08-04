from __future__ import annotations

from typing import Any


class RegressionService:
    """Compare aggregate experiment metrics against an immutable baseline."""

    def compare(
        self,
        current: dict[str, float],
        baseline: dict[str, float],
        thresholds: dict[str, float],
    ) -> dict[str, Any]:
        rules = {
            "quality": ("decrease", thresholds.get("quality_drop", 3.0)),
            "cost": ("increase", thresholds.get("cost_increase", 10.0)),
            "latency": ("increase", thresholds.get("latency_increase", 15.0)),
            "error_rate": ("increase", thresholds.get("error_rate_increase", 2.0)),
            "json_schema": ("decrease", thresholds.get("json_schema_drop", 3.0)),
            "stability": ("decrease", thresholds.get("stability_drop", 5.0)),
        }
        changes: dict[str, dict[str, Any]] = {}
        critical = False
        warning = False
        for metric, (direction, limit) in rules.items():
            old = baseline.get(metric)
            new = current.get(metric)
            if old is None or new is None:
                continue
            percent = ((new - old) / abs(old) * 100) if old else (100.0 if new else 0.0)
            degradation = -percent if direction == "decrease" else percent
            breached = degradation > limit
            critical = critical or degradation > limit * 2
            warning = warning or breached
            changes[metric] = {
                "baseline": old,
                "current": new,
                "change_percent": percent,
                "threshold_percent": limit,
                "regression": breached,
            }
        status = "critical" if critical else "warning" if warning else "none"
        return {"status": status, "metric_changes": changes}


regression_service = RegressionService()
