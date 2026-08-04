from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = []
    prompt_version_id: uuid.UUID
    dataset_version_id: uuid.UUID
    model_ids: list[uuid.UUID] = Field(min_length=1)
    parameters: dict[str, Any] = {}
    evaluator_config: dict[str, Any] = {"json_validator": {}, "exact_match": {}}
    recommendation_weights: dict[str, float] = {
        "quality": 0.45,
        "cost": 0.25,
        "latency": 0.15,
        "stability": 0.10,
        "error_rate": 0.05,
    }
    regression_thresholds: dict[str, float] = {
        "quality_drop": 3,
        "cost_increase": 10,
        "latency_increase": 15,
        "error_rate_increase": 2,
    }
    baseline_experiment_id: uuid.UUID | None = None
    maximum_budget: float | None = Field(default=None, gt=0)
    currency: str = Field(default="PLN", pattern="^(PLN|USD|EUR)$")

    @model_validator(mode="after")
    def validate_weights(self) -> ExperimentCreate:
        if abs(sum(self.recommendation_weights.values()) - 1.0) > 0.001:
            raise ValueError("Recommendation weights must sum to 1.0")
        return self


class ManualReviewCreate(BaseModel):
    stars: int | None = Field(default=None, ge=1, le=5)
    is_correct: bool | None = None
    is_useful: bool | None = None
    comment: str | None = Field(default=None, max_length=5000)
    error_labels: list[str] = []
