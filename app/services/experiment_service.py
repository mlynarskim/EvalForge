from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
from app.evaluators.base import EvaluationContext
from app.models import (
    DatasetVersion,
    EvaluationResult,
    Experiment,
    ExperimentModel,
    ExperimentRun,
    LLMModel,
    ModelPricing,
    PromptVersion,
    ProviderCredential,
    TestCase,
)
from app.models.entities import ExperimentStatus, utcnow
from app.providers import GenerateRequest, ProviderError, ProviderRegistry
from app.services.encryption_service import EncryptionService
from app.services.evaluation_service import evaluation_service
from app.services.pricing_service import pricing_service

VARIABLE_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*}}")


def render_template(template: str, values: dict[str, Any]) -> str:
    """Render a constrained variable template without evaluating user supplied code."""

    def replace(match: re.Match[str]) -> str:
        path = match.group(1)
        value: Any = values
        for key in path.split("."):
            if not isinstance(value, dict) or key not in value:
                raise ValueError(f"Missing template variable: {path}")
            value = value[key]
        return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value

    return VARIABLE_PATTERN.sub(replace, template)


def extract_variables(template: str) -> list[str]:
    return sorted(set(VARIABLE_PATTERN.findall(template)))


class ExperimentService:
    """Create immutable experiment plans and execute their runs concurrently."""

    def create(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: Any,
    ) -> Experiment:
        prompt_version = db.scalar(
            select(PromptVersion)
            .join(PromptVersion.prompt)
            .where(PromptVersion.id == payload.prompt_version_id)
        )
        dataset_version = db.scalar(
            select(DatasetVersion)
            .join(DatasetVersion.dataset)
            .where(DatasetVersion.id == payload.dataset_version_id)
        )
        if not prompt_version or prompt_version.prompt.workspace_id != workspace_id:
            raise ValueError("Prompt version is unavailable")
        if not dataset_version or dataset_version.dataset.workspace_id != workspace_id:
            raise ValueError("Dataset version is unavailable")
        models = list(
            db.scalars(
                select(LLMModel).where(
                    LLMModel.id.in_(payload.model_ids),
                    LLMModel.workspace_id == workspace_id,
                    LLMModel.is_active.is_(True),
                )
            )
        )
        if len(models) != len(set(payload.model_ids)):
            raise ValueError("One or more selected models are unavailable")
        experiment = Experiment(
            workspace_id=workspace_id,
            created_by_id=user_id,
            name=payload.name,
            description=payload.description,
            tags=payload.tags,
            prompt_version_id=prompt_version.id,
            dataset_version_id=dataset_version.id,
            baseline_experiment_id=payload.baseline_experiment_id,
            parameters=payload.parameters,
            evaluator_config=payload.evaluator_config,
            recommendation_weights=payload.recommendation_weights,
            regression_thresholds=payload.regression_thresholds,
            maximum_budget=payload.maximum_budget,
            currency=payload.currency,
        )
        db.add(experiment)
        db.flush()
        for model in models:
            latest_price = db.scalar(
                select(ModelPricing)
                .where(ModelPricing.model_id == model.id)
                .order_by(ModelPricing.effective_from.desc())
                .limit(1)
            )
            pricing_snapshot = None
            if latest_price:
                pricing_snapshot = {
                    "input_price_per_million": latest_price.input_price_per_million,
                    "output_price_per_million": latest_price.output_price_per_million,
                    "cached_input_price_per_million": latest_price.cached_input_price_per_million,
                    "currency": latest_price.currency,
                    "effective_from": latest_price.effective_from.isoformat(),
                }
            db.add(
                ExperimentModel(
                    experiment_id=experiment.id,
                    model_id=model.id,
                    pricing_snapshot=pricing_snapshot,
                    normalized_parameters=payload.parameters,
                )
            )
        db.commit()
        return experiment

    def prepare_runs(self, db: Session, experiment_id: uuid.UUID) -> int:
        experiment = db.scalar(
            select(Experiment)
            .options(
                selectinload(Experiment.models)
                .selectinload(ExperimentModel.model)
                .selectinload(LLMModel.provider),
            )
            .where(Experiment.id == experiment_id)
        )
        if not experiment:
            raise ValueError("Experiment does not exist")
        if experiment.status not in {ExperimentStatus.DRAFT, ExperimentStatus.PAUSED}:
            raise ValueError("Experiment cannot be queued from its current state")
        prompt = db.get(PromptVersion, experiment.prompt_version_id)
        test_cases = list(
            db.scalars(
                select(TestCase).where(TestCase.dataset_version_id == experiment.dataset_version_id)
            )
        )
        if not prompt or not test_cases:
            raise ValueError("Experiment prompt or dataset is unavailable")
        existing = db.scalar(
            select(func.count())
            .select_from(ExperimentRun)
            .where(ExperimentRun.experiment_id == experiment.id)
        )
        if not existing:
            repetitions = max(1, min(int(experiment.parameters.get("repetitions", 1)), 20))
            for selected in experiment.models:
                for case in test_cases:
                    for repetition in range(1, repetitions + 1):
                        db.add(
                            ExperimentRun(
                                experiment_id=experiment.id,
                                model_id=selected.model_id,
                                test_case_id=case.id,
                                repetition=repetition,
                                provider_key=selected.model.provider.key,
                                provider_model_id=selected.model.model_id,
                                prompt_snapshot={
                                    "version": prompt.version,
                                    "system_prompt": prompt.system_prompt,
                                    "user_template": prompt.user_template,
                                    "response_format": prompt.response_format,
                                    "json_schema": prompt.json_schema,
                                },
                                dataset_snapshot={
                                    "name": case.name,
                                    "inputs": case.inputs,
                                    "expected_output": case.expected_output,
                                    "expected_keywords": case.expected_keywords,
                                    "reference_context": case.reference_context,
                                    "metadata": case.extra_metadata,
                                },
                                parameter_snapshot=selected.normalized_parameters,
                                pricing_snapshot=selected.pricing_snapshot,
                            )
                        )
        experiment.status = ExperimentStatus.QUEUED
        db.commit()
        return (
            len(experiment.models)
            * len(test_cases)
            * int(experiment.parameters.get("repetitions", 1))
        )

    async def execute(self, experiment_id: uuid.UUID) -> None:
        with SessionLocal() as db:
            experiment = db.get(Experiment, experiment_id)
            if not experiment:
                raise ValueError("Experiment does not exist")
            experiment.status = ExperimentStatus.RUNNING
            experiment.started_at = experiment.started_at or utcnow()
            db.commit()
            run_ids = list(
                db.scalars(
                    select(ExperimentRun.id).where(
                        ExperimentRun.experiment_id == experiment_id,
                        ExperimentRun.status.in_(["queued", "failed"]),
                    )
                )
            )
            concurrency = max(1, min(int(experiment.parameters.get("concurrency", 4)), 20))
        semaphore = asyncio.Semaphore(concurrency)

        async def limited(run_id: uuid.UUID) -> None:
            async with semaphore:
                await self._execute_run(run_id)
                self._update_progress(experiment_id)

        await asyncio.gather(*(limited(run_id) for run_id in run_ids))
        with SessionLocal() as db:
            experiment = db.get(Experiment, experiment_id)
            if not experiment or experiment.status == ExperimentStatus.CANCELLED:
                return
            errors = db.scalar(
                select(func.count())
                .select_from(ExperimentRun)
                .where(
                    ExperimentRun.experiment_id == experiment_id, ExperimentRun.status == "failed"
                )
            )
            experiment.status = (
                ExperimentStatus.COMPLETED_WITH_ERRORS if errors else ExperimentStatus.COMPLETED
            )
            experiment.completed_at = utcnow()
            experiment.progress = 100.0
            experiment.total_cost = float(
                db.scalar(
                    select(func.sum(ExperimentRun.total_cost)).where(
                        ExperimentRun.experiment_id == experiment_id
                    )
                )
                or 0
            )
            db.commit()

    async def _execute_run(self, run_id: uuid.UUID) -> None:
        encryption = EncryptionService()
        with SessionLocal() as db:
            run = db.get(ExperimentRun, run_id)
            if not run:
                return
            experiment = db.get(Experiment, run.experiment_id)
            model = db.get(LLMModel, run.model_id)
            if not experiment or not model or experiment.status == ExperimentStatus.CANCELLED:
                return
            credential = db.scalar(
                select(ProviderCredential).where(
                    ProviderCredential.workspace_id == experiment.workspace_id,
                    ProviderCredential.provider_id == model.provider_id,
                )
            )
            api_key = (
                encryption.decrypt(credential.encrypted_api_key)
                if credential and credential.encrypted_api_key
                else None
            )
            base_url = (
                encryption.decrypt(credential.encrypted_base_url)
                if credential and credential.encrypted_base_url
                else None
            )
            provider = ProviderRegistry.create(run.provider_key, api_key, base_url)
            snapshot = run.dataset_snapshot
            prompt_snapshot = run.prompt_snapshot
            request = GenerateRequest(
                model=run.provider_model_id,
                system_prompt=prompt_snapshot["system_prompt"],
                user_prompt=render_template(prompt_snapshot["user_template"], snapshot["inputs"]),
                temperature=run.parameter_snapshot.get("temperature"),
                max_output_tokens=run.parameter_snapshot.get("max_output_tokens"),
                top_p=run.parameter_snapshot.get("top_p"),
                seed=run.parameter_snapshot.get("seed"),
                response_format=prompt_snapshot.get("response_format", "text"),
                json_schema=prompt_snapshot.get("json_schema"),
                timeout=float(run.parameter_snapshot.get("timeout", 60)),
            )
            run.status = "running"
            run.started_at = utcnow()
            db.commit()
        maximum_retries = max(0, min(int(run.parameter_snapshot.get("max_retries", 2)), 5))
        started = time.perf_counter()
        try:
            for attempt in range(maximum_retries + 1):
                try:
                    response = await provider.generate(request)
                    break
                except ProviderError as provider_error:
                    if not provider_error.retryable or attempt >= maximum_retries:
                        raise
                    await asyncio.sleep(min(2**attempt, 8))
            latency_ms = (time.perf_counter() - started) * 1000
            pricing = run.pricing_snapshot or {}
            cost = pricing_service.calculate(response.usage, pricing, experiment.currency)
            context = EvaluationContext(
                response=response.text,
                expected_output=snapshot.get("expected_output"),
                expected_keywords=snapshot.get("expected_keywords", []),
                json_schema=prompt_snapshot.get("json_schema"),
                reference_context=snapshot.get("reference_context"),
                inputs=snapshot.get("inputs", {}),
            )
            outcomes = await evaluation_service.evaluate(context, experiment.evaluator_config)
            with SessionLocal() as db:
                persisted = db.get(ExperimentRun, run_id)
                if not persisted:
                    return
                persisted.status = "completed"
                persisted.finished_at = utcnow()
                persisted.latency_ms = latency_ms
                persisted.raw_response = response.text
                try:
                    persisted.parsed_response = json.loads(response.text)
                except json.JSONDecodeError:
                    persisted.parsed_response = None
                persisted.input_tokens = response.usage.input_tokens
                persisted.output_tokens = response.usage.output_tokens
                persisted.reasoning_tokens = response.usage.reasoning_tokens
                persisted.cached_tokens = response.usage.cached_tokens
                persisted.input_cost = cost.input_cost
                persisted.output_cost = cost.output_cost
                persisted.total_cost = cost.total_cost
                persisted.retry_count = attempt
                for outcome in outcomes:
                    db.add(
                        EvaluationResult(
                            run_id=run_id,
                            evaluator=outcome.evaluator,
                            score=outcome.score,
                            passed=outcome.passed,
                            details=outcome.details,
                            is_automated_judge=outcome.is_automated_judge,
                        )
                    )
                db.commit()
        except Exception as exc:
            normalized_error = (
                exc if isinstance(exc, ProviderError) else provider.normalize_error(exc)
            )
            with SessionLocal() as db:
                persisted = db.get(ExperimentRun, run_id)
                if persisted:
                    persisted.status = "failed"
                    persisted.finished_at = utcnow()
                    persisted.latency_ms = (time.perf_counter() - started) * 1000
                    persisted.error_category = normalized_error.category
                    persisted.error_message = str(normalized_error)[:1000]
                    db.commit()

    def _update_progress(self, experiment_id: uuid.UUID) -> None:
        with SessionLocal() as db:
            experiment = db.get(Experiment, experiment_id)
            if not experiment:
                return
            total = (
                db.scalar(
                    select(func.count())
                    .select_from(ExperimentRun)
                    .where(ExperimentRun.experiment_id == experiment_id)
                )
                or 0
            )
            finished = (
                db.scalar(
                    select(func.count())
                    .select_from(ExperimentRun)
                    .where(
                        ExperimentRun.experiment_id == experiment_id,
                        ExperimentRun.status.in_(["completed", "failed"]),
                    )
                )
                or 0
            )
            total_cost = float(
                db.scalar(
                    select(func.sum(ExperimentRun.total_cost)).where(
                        ExperimentRun.experiment_id == experiment_id
                    )
                )
                or 0
            )
            experiment.progress = finished / total * 100 if total else 0.0
            experiment.total_cost = total_cost
            if experiment.maximum_budget and total_cost >= experiment.maximum_budget:
                experiment.status = ExperimentStatus.CANCELLED
            db.commit()


experiment_service = ExperimentService()
