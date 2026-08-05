from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import func, select

from app.models import (
    DatasetVersion,
    Experiment,
    ExperimentRun,
    LLMModel,
    PromptVersion,
    Provider,
    User,
    WorkspaceMember,
)
from app.models.entities import ExperimentStatus
from app.providers.base import (
    BaseModelProvider,
    GenerateRequest,
    GenerateResponse,
    ModelInfo,
    TokenUsage,
)
from app.providers.ollama_provider import OllamaProvider
from app.providers.registry import ProviderRegistry
from app.schemas.experiment import ExperimentCreate
from app.services.demo_service import seed_demo
from app.services.experiment_service import experiment_service


class FakeProvider(BaseModelProvider):
    key = "ollama"

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo("demo/support-classifier", "Demo Support Classifier")]

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(
            text=(
                '{"category":"question","priority":"low",'
                '"summary":"Classified support ticket","requires_human":false}'
            ),
            usage=TokenUsage(input_tokens=100, output_tokens=30),
            raw={"model": request.model},
            finish_reason="stop",
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[str]:
        yield (await self.generate(request)).text

    def normalize_usage(self, response: dict[str, Any]) -> TokenUsage:
        return TokenUsage()

    async def validate_credentials(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_experiment_is_prepared_executed_and_persisted(db) -> None:
    seed_demo(db)
    user = db.scalar(select(User))
    membership = db.scalar(select(WorkspaceMember))
    prompt_version = db.scalar(select(PromptVersion))
    dataset_version = db.scalar(select(DatasetVersion))
    provider = db.scalar(select(Provider).where(Provider.key == "ollama"))
    assert user and membership and prompt_version and dataset_version and provider
    model = LLMModel(
        workspace_id=membership.workspace_id,
        provider_id=provider.id,
        model_id="test/execution-model",
        display_name="Execution Test Model",
        family="test",
        is_manual=True,
        supports_json_mode=True,
    )
    db.add(model)
    db.commit()
    payload = ExperimentCreate(
        name="Execution integration test",
        prompt_version_id=prompt_version.id,
        dataset_version_id=dataset_version.id,
        model_ids=[model.id],
        parameters={"concurrency": 3, "max_retries": 1, "timeout": 5},
        evaluator_config={"json_validator": {}, "schema_validator": {}},
        maximum_budget=1,
        currency="PLN",
    )
    experiment = experiment_service.create(db, membership.workspace_id, user.id, payload)
    assert experiment_service.prepare_runs(db, experiment.id) == 20
    ProviderRegistry.register("ollama", FakeProvider)
    try:
        await experiment_service.execute(experiment.id)
    finally:
        ProviderRegistry.register("ollama", OllamaProvider)
    db.expire_all()
    persisted = db.get(Experiment, experiment.id)
    assert persisted is not None
    assert persisted.status == ExperimentStatus.COMPLETED
    assert persisted.progress == 100
    assert (
        db.scalar(
            select(func.count())
            .select_from(ExperimentRun)
            .where(
                ExperimentRun.experiment_id == experiment.id, ExperimentRun.status == "completed"
            )
        )
        == 20
    )
