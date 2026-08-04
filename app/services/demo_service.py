from __future__ import annotations

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
    TestCase,
    User,
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


def seed_demo(db: Session) -> None:
    """Create providers and an explicitly labelled, cost free demonstration workspace."""
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
    user = db.scalar(select(User).where(User.email == settings.demo_admin_email))
    if user:
        return
    user, workspace = auth_service.register(
        db,
        settings.demo_admin_email,
        settings.demo_admin_password,
        "Demo Admin",
        settings.default_language,
    )
    user.is_demo = True
    prompt = Prompt(
        workspace_id=workspace.id,
        name="Customer support classification",
        description="Demo prompt for structured ticket classification.",
        tags=["demo", "classification"],
        created_by_id=user.id,
    )
    db.add(prompt)
    db.flush()
    prompt_version = PromptVersion(
        prompt_id=prompt.id,
        version=1,
        system_prompt="You classify customer support tickets. Return only valid JSON.",
        user_template="Classify this ticket:\n\n{{input_text}}",
        variables=["input_text"],
        response_format="json_schema",
        json_schema=DEMO_SCHEMA,
        created_by_id=user.id,
    )
    db.add(prompt_version)
    dataset = Dataset(
        workspace_id=workspace.id,
        name="Customer support tickets",
        description="Twenty representative demonstration cases.",
        tags=["demo", "support"],
        created_by_id=user.id,
    )
    db.add(dataset)
    db.flush()
    dataset_version = DatasetVersion(
        dataset_id=dataset.id,
        version=1,
        required_variables=["input_text"],
        created_by_id=user.id,
    )
    db.add(dataset_version)
    db.flush()
    test_cases = []
    for name, text, category, priority in DEMO_CASES:
        case = TestCase(
            dataset_version_id=dataset_version.id,
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
        test_cases.append(case)
    provider = db.scalar(select(Provider).where(Provider.key == "ollama"))
    if provider is None:
        raise RuntimeError("Ollama provider was not initialized")
    db.flush()
    model = LLMModel(
        workspace_id=workspace.id,
        provider_id=provider.id,
        model_id="demo/support-classifier",
        display_name="Demo Support Classifier",
        family="demo",
        is_manual=True,
        supports_json_mode=True,
        supports_json_schema=True,
    )
    db.add(model)
    db.flush()
    experiment = Experiment(
        workspace_id=workspace.id,
        name="Customer support baseline",
        description="Demonstration results. No provider API was called.",
        tags=["demo"],
        status=ExperimentStatus.COMPLETED,
        prompt_version_id=prompt_version.id,
        dataset_version_id=dataset_version.id,
        parameters={"temperature": 0, "repetitions": 1},
        evaluator_config={"json_validator": {}, "schema_validator": {}},
        recommendation_weights={
            "quality": 0.45,
            "cost": 0.25,
            "latency": 0.15,
            "stability": 0.10,
            "error_rate": 0.05,
        },
        regression_thresholds={},
        currency="PLN",
        is_demo=True,
        progress=100,
        total_cost=0,
        started_at=utcnow() - timedelta(minutes=5),
        completed_at=utcnow(),
        created_by_id=user.id,
    )
    db.add(experiment)
    db.flush()
    db.add(
        ExperimentModel(
            experiment_id=experiment.id,
            model_id=model.id,
            pricing_snapshot={"currency": "PLN"},
            normalized_parameters={"temperature": 0},
        )
    )
    for index, case in enumerate(test_cases):
        expected = case.expected_output
        if not isinstance(expected, dict):
            raise RuntimeError("Demo expected output must be an object")
        response = expected if index not in {5, 14} else {**expected, "priority": "low"}
        run = ExperimentRun(
            experiment_id=experiment.id,
            model_id=model.id,
            test_case_id=case.id,
            status="completed",
            provider_key="ollama",
            provider_model_id=model.model_id,
            prompt_snapshot={"version": 1},
            dataset_snapshot={"name": case.name, "inputs": case.inputs},
            parameter_snapshot={"temperature": 0},
            pricing_snapshot={"currency": "PLN"},
            raw_response=str(response)
            .replace("'", '"')
            .replace("True", "true")
            .replace("False", "false"),
            parsed_response=response,
            started_at=experiment.started_at,
            finished_at=experiment.completed_at,
            latency_ms=420 + index * 31,
            input_tokens=85 + index,
            output_tokens=42,
        )
        db.add(run)
        db.flush()
        passed = index not in {5, 14}
        db.add(
            EvaluationResult(
                run_id=run.id,
                evaluator="schema_validator",
                score=float(passed),
                passed=passed,
                details={"demo": True, "errors": [] if passed else ["Incorrect priority"]},
            )
        )
    db.commit()
