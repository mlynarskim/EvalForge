from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Dataset,
    DatasetVersion,
    EvaluationResult,
    Experiment,
    ExperimentModel,
    ExperimentRun,
    LLMModel,
    Prompt,
    PromptVersion,
    Provider,
    ProviderCredential,
    TestCase,
    User,
    Workspace,
    WorkspaceMember,
)
from app.models.entities import ExperimentStatus, utcnow
from app.providers import ProviderRegistry
from app.services.auth_service import auth_service

PROVIDER_NAMES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic Claude",
    "gemini": "Google Gemini",
    "mistral": "Mistral AI",
    "openrouter": "OpenRouter",
    "ollama": "Ollama",
}

DEMO_CASES = [
    (
        "Late delivery",
        "My parcel is five days late and no one can tell me where it is.",
        "complaint",
        "high",
    ),
    ("Invoice question", "Where can I download an invoice for order 1842?", "question", "low"),
    (
        "Duplicate charge",
        "I was charged twice. Please return the second payment.",
        "refund",
        "high",
    ),
    (
        "Application crash",
        "The desktop application closes when I upload a PDF.",
        "technical_issue",
        "high",
    ),
    ("Address change", "Can I update the delivery address before dispatch?", "question", "medium"),
    ("Damaged item", "The screen arrived cracked and the box was damaged.", "complaint", "high"),
    ("Password reset", "The reset link says it has already expired.", "technical_issue", "medium"),
    (
        "Subscription cancellation",
        "Please cancel my plan at the end of this month.",
        "other",
        "medium",
    ),
    ("Wrong size", "I received medium instead of the large size I ordered.", "complaint", "medium"),
    (
        "Refund status",
        "It has been ten days since my return. When will I get the money?",
        "refund",
        "medium",
    ),
    ("Feature availability", "Does the team plan include audit history?", "question", "low"),
    ("Login failure", "I get error 403 every time I sign in.", "technical_issue", "high"),
    ("Missing accessory", "The charger was not included in the package.", "complaint", "medium"),
    ("Trial extension", "Could you extend our trial by one week?", "other", "low"),
    (
        "Card rejected",
        "My valid business card is rejected during checkout.",
        "technical_issue",
        "high",
    ),
    ("Return request", "The product is unused and I want to return it.", "refund", "medium"),
    ("Opening hours", "Is support available on Sunday?", "question", "low"),
    ("Account deletion", "Delete my account and all associated data.", "other", "high"),
    ("Incorrect invoice", "The company tax number on my invoice is wrong.", "complaint", "medium"),
    (
        "Export unavailable",
        "CSV export stays at zero percent and never completes.",
        "technical_issue",
        "medium",
    ),
]

DEMO_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["category", "priority", "summary", "requires_human"],
    "properties": {
        "category": {
            "type": "string",
            "enum": ["complaint", "question", "refund", "technical_issue", "other"],
        },
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary": {"type": "string", "minLength": 5},
        "requires_human": {"type": "boolean"},
    },
    "additionalProperties": False,
}


@dataclass(frozen=True)
class DemoModelSpec:
    key: str
    name: str
    description: str
    quality: float
    latency_ms: int
    total_cost_eur: float
    failed_cases: frozenset[int]


DEMO_MODELS = (
    DemoModelSpec(
        "atlas",
        "Atlas Reasoning",
        "Highest quality model for accuracy focused workloads.",
        0.96,
        1280,
        0.0184,
        frozenset({14}),
    ),
    DemoModelSpec(
        "pulse",
        "Pulse Balanced",
        "Balanced model recommended for this quality, latency and cost profile.",
        0.92,
        690,
        0.0062,
        frozenset({5, 14}),
    ),
    DemoModelSpec(
        "nova",
        "Nova Fast",
        "Fastest and least expensive model with lower task reliability.",
        0.85,
        310,
        0.0018,
        frozenset({3, 5, 11, 14, 19}),
    ),
)


def _demo_user_and_workspace(db: Session) -> tuple[User, Workspace]:
    user = db.scalar(select(User).where(User.email == settings.demo_admin_email))
    if user is None:
        user, workspace = auth_service.register(
            db,
            settings.demo_admin_email,
            settings.demo_admin_password,
            "Demo Admin",
            settings.default_language,
        )
    else:
        membership = db.scalar(
            select(WorkspaceMember).where(WorkspaceMember.user_id == user.id).limit(1)
        )
        if membership is None:
            raise RuntimeError("Demo user has no workspace")
        existing_workspace = db.get(Workspace, membership.workspace_id)
        if existing_workspace is None:
            raise RuntimeError("Demo workspace is unavailable")
        workspace = existing_workspace
    user.is_demo = True
    workspace.default_currency = "EUR"
    return user, workspace


def _demo_prompt(db: Session, user: User, workspace: Workspace) -> PromptVersion:
    prompt = db.scalar(
        select(Prompt).where(
            Prompt.workspace_id == workspace.id,
            Prompt.name == "Customer support classification",
        )
    )
    if prompt is None:
        prompt = Prompt(
            workspace_id=workspace.id,
            name="Customer support classification",
            description="Classify support tickets into structured JSON for routing and prioritisation.",
            tags=["demo", "classification", "json"],
            created_by_id=user.id,
        )
        db.add(prompt)
        db.flush()
    version = db.scalar(
        select(PromptVersion)
        .where(PromptVersion.prompt_id == prompt.id)
        .order_by(PromptVersion.version.desc())
        .limit(1)
    )
    if version is None:
        version = PromptVersion(
            prompt_id=prompt.id,
            version=1,
            system_prompt=(
                "You classify customer support tickets. Return only valid JSON matching the "
                "provided schema. Escalate high priority cases to a human."
            ),
            user_template="Classify this customer support ticket:\n\n{{input_text}}",
            variables=["input_text"],
            response_format="json_schema",
            json_schema=DEMO_SCHEMA,
            change_note="Initial demonstration prompt",
            created_by_id=user.id,
        )
        db.add(version)
        db.flush()
    return version


def _demo_dataset(
    db: Session, user: User, workspace: Workspace
) -> tuple[DatasetVersion, list[TestCase]]:
    dataset = db.scalar(
        select(Dataset).where(
            Dataset.workspace_id == workspace.id,
            Dataset.name == "Customer support tickets",
        )
    )
    if dataset is None:
        dataset = Dataset(
            workspace_id=workspace.id,
            name="Customer support tickets",
            description="Twenty representative support cases covering urgency and intent.",
            tags=["demo", "support", "structured-output"],
            created_by_id=user.id,
        )
        db.add(dataset)
        db.flush()
    version = db.scalar(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version.desc())
        .limit(1)
    )
    if version is None:
        version = DatasetVersion(
            dataset_id=dataset.id,
            version=1,
            required_variables=["input_text"],
            change_note="Initial demonstration dataset",
            created_by_id=user.id,
        )
        db.add(version)
        db.flush()
    cases_by_name = {
        item.name: item
        for item in db.scalars(select(TestCase).where(TestCase.dataset_version_id == version.id))
    }
    for name, text, category, priority in DEMO_CASES:
        if name in cases_by_name:
            continue
        case = TestCase(
            dataset_version_id=version.id,
            name=name,
            inputs={"input_text": text},
            expected_output={
                "category": category,
                "priority": priority,
                "summary": text[:80],
                "requires_human": priority == "high",
            },
            expected_keywords=[category, priority],
            difficulty="medium" if priority != "low" else "easy",
            extra_metadata={"category": "customer_support", "demo": True},
        )
        db.add(case)
        db.flush()
        cases_by_name[name] = case
    return version, [cases_by_name[name] for name, *_ in DEMO_CASES]


def _demo_models(db: Session, workspace: Workspace) -> list[LLMModel]:
    provider = db.scalar(select(Provider).where(Provider.key == "simulated"))
    if provider is None:
        provider = Provider(
            key="simulated",
            display_name="EvalForge Simulator",
            supports_model_sync=False,
        )
        db.add(provider)
        db.flush()
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace.id,
            ProviderCredential.provider_id == provider.id,
        )
    )
    if credential is None:
        credential = ProviderCredential(
            workspace_id=workspace.id,
            provider_id=provider.id,
            masked_value="No API key required",
            connection_status="connected",
        )
        db.add(credential)
    models: list[LLMModel] = []
    for spec in DEMO_MODELS:
        model = db.scalar(
            select(LLMModel).where(
                LLMModel.workspace_id == workspace.id,
                LLMModel.provider_id == provider.id,
                LLMModel.model_id == f"demo/{spec.key}",
            )
        )
        if model is None:
            model = LLMModel(
                workspace_id=workspace.id,
                provider_id=provider.id,
                model_id=f"demo/{spec.key}",
                display_name=spec.name,
                family="demo",
                category="simulated",
                is_manual=True,
                supports_json_mode=True,
                supports_json_schema=True,
                context_window=128_000,
                max_output_tokens=4_096,
            )
            db.add(model)
            db.flush()
        model.display_name = spec.name
        model.status = "active"
        model.is_active = True
        models.append(model)
    selected_ids = {model.id for model in models}
    for legacy in db.scalars(
        select(LLMModel).where(
            LLMModel.workspace_id == workspace.id,
            LLMModel.family == "demo",
        )
    ):
        if legacy.id not in selected_ids:
            legacy.is_active = False
    return models


def _response_for(
    case: TestCase, spec: DemoModelSpec, index: int
) -> tuple[dict[str, object], bool]:
    expected = case.expected_output
    if not isinstance(expected, dict):
        raise RuntimeError("Demo expected output must be an object")
    response: dict[str, object] = dict(expected)
    passed = index not in spec.failed_cases
    if not passed:
        response["priority"] = "low" if expected.get("priority") != "low" else "medium"
        response["requires_human"] = False
    return response, passed


def _populate_experiment(
    db: Session,
    experiment: Experiment,
    models: list[LLMModel],
    cases: list[TestCase],
) -> None:
    expected_run_count = len(models) * len(cases)
    current_model_ids = {item.model_id for item in experiment.models}
    target_model_ids = {item.id for item in models}
    if (
        "seed:v2" in (experiment.tags or [])
        and len(experiment.runs) == expected_run_count
        and current_model_ids == target_model_ids
    ):
        return
    experiment.runs.clear()
    experiment.models.clear()
    db.flush()
    experiment.tags = ["demo", "simulated", "seed:v2"]
    experiment.total_cost = round(sum(item.total_cost_eur for item in DEMO_MODELS), 5)
    for model, spec in zip(models, DEMO_MODELS, strict=True):
        db.add(
            ExperimentModel(
                experiment_id=experiment.id,
                model_id=model.id,
                pricing_snapshot={
                    "currency": "EUR",
                    "simulated": True,
                    "estimated_total": spec.total_cost_eur,
                },
                normalized_parameters={"temperature": 0, "simulation": True},
            )
        )
        for index, case in enumerate(cases):
            response, passed = _response_for(case, spec, index)
            json_valid = not (spec.key == "nova" and index == len(cases) - 1)
            raw_response = json.dumps(response, ensure_ascii=False)
            if not json_valid:
                raw_response = raw_response[:-1]
                passed = False
            case_cost = spec.total_cost_eur / len(cases)
            run = ExperimentRun(
                experiment_id=experiment.id,
                model_id=model.id,
                test_case_id=case.id,
                status="completed",
                provider_key="simulated",
                provider_model_id=model.model_id,
                prompt_snapshot={"version": 1, "simulated": True},
                dataset_snapshot={"name": case.name, "inputs": case.inputs},
                parameter_snapshot={"temperature": 0, "simulation": True},
                pricing_snapshot={"currency": "EUR", "simulated": True},
                raw_response=raw_response,
                parsed_response=response if json_valid else None,
                started_at=experiment.started_at,
                finished_at=experiment.completed_at,
                latency_ms=spec.latency_ms + index * 23,
                time_to_first_token_ms=(spec.latency_ms + index * 23) * 0.35,
                input_tokens=82 + index,
                output_tokens=38 + index % 7,
                input_cost=case_cost * 0.45,
                output_cost=case_cost * 0.55,
                total_cost=case_cost,
            )
            db.add(run)
            db.flush()
            score = spec.quality - (index % 4) * 0.01 if passed else 0.56 + (index % 3) * 0.03
            db.add(
                EvaluationResult(
                    run_id=run.id,
                    evaluator="structured_task_accuracy",
                    score=round(score, 3),
                    passed=passed,
                    details={
                        "simulated": True,
                        "json_valid": json_valid,
                        "expected": case.expected_output,
                    },
                )
            )


def seed_demo(db: Session) -> None:
    """Create or upgrade a complete, cost free demonstration workspace."""
    for key in ProviderRegistry.available_keys():
        if not db.scalar(select(Provider).where(Provider.key == key)):
            db.add(
                Provider(
                    key=key,
                    display_name=PROVIDER_NAMES[key],
                    supports_model_sync=True,
                )
            )
    db.commit()
    if not settings.demo_mode:
        return
    user, workspace = _demo_user_and_workspace(db)
    prompt_version = _demo_prompt(db, user, workspace)
    dataset_version, cases = _demo_dataset(db, user, workspace)
    models = _demo_models(db, workspace)
    experiment = db.scalar(
        select(Experiment).where(
            Experiment.workspace_id == workspace.id,
            Experiment.name == "Customer support model comparison",
        )
    )
    if experiment is None:
        experiment = db.scalar(
            select(Experiment).where(
                Experiment.workspace_id == workspace.id,
                Experiment.name == "Customer support baseline",
            )
        )
    if experiment is None:
        experiment = Experiment(
            workspace_id=workspace.id,
            name="Customer support model comparison",
            prompt_version_id=prompt_version.id,
            dataset_version_id=dataset_version.id,
            created_by_id=user.id,
        )
        db.add(experiment)
        db.flush()
    experiment.name = "Customer support model comparison"
    experiment.description = (
        "A complete simulated comparison across three fictional models and twenty support "
        "cases. No external provider API was called."
    )
    experiment.status = ExperimentStatus.COMPLETED
    experiment.prompt_version_id = prompt_version.id
    experiment.dataset_version_id = dataset_version.id
    experiment.parameters = {"temperature": 0, "repetitions": 1, "simulation": True}
    experiment.evaluator_config = {"structured_task_accuracy": {"simulated": True}}
    experiment.recommendation_weights = {
        "quality": 0.45,
        "cost": 0.25,
        "latency": 0.15,
        "stability": 0.10,
        "error_rate": 0.05,
    }
    experiment.regression_thresholds = {"minimum_quality": 0.7}
    experiment.maximum_budget = 0.05
    experiment.currency = "EUR"
    experiment.is_demo = True
    experiment.progress = 100
    experiment.started_at = utcnow() - timedelta(seconds=48)
    experiment.completed_at = utcnow()
    _populate_experiment(db, experiment, models, cases)
    db.commit()
