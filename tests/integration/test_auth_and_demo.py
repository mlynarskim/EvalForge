import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.main import app
from app.models import Experiment, ExperimentRun, LLMModel, Provider, User
from app.models import TestCase as DatasetCase
from app.services.auth_service import auth_service
from app.services.demo_service import seed_demo
from app.services.metrics_service import metrics_service
from app.services.recommendation_service import recommendation_service


def test_registration_authentication_and_signed_token(db) -> None:
    user, workspace = auth_service.register(
        db, "Ada@Example.com", "A-secure-password-123", "Ada", "pl"
    )
    assert user.email == "ada@example.com"
    assert workspace.owner_id == user.id
    authenticated = auth_service.authenticate(db, "ada@example.com", "A-secure-password-123")
    token = auth_service.create_token(authenticated)
    resolved = auth_service.resolve_token(db, token)
    assert resolved.id == user.id


def test_demo_seed_is_idempotent_and_contains_complete_comparison(db) -> None:
    seed_demo(db)
    seed_demo(db)
    assert db.scalar(select(func.count()).select_from(User)) == 1
    assert db.scalar(select(func.count()).select_from(DatasetCase)) == 20
    assert (
        db.scalar(
            select(func.count())
            .select_from(LLMModel)
            .where(LLMModel.is_active.is_(True), LLMModel.family == "demo")
        )
        == 3
    )
    assert db.scalar(select(func.count()).select_from(ExperimentRun)) == 60
    experiment = db.scalar(
        select(Experiment).options(
            selectinload(Experiment.runs).selectinload(ExperimentRun.evaluations)
        )
    )
    assert experiment is not None
    assert experiment.is_demo is True
    assert experiment.total_cost > 0
    metrics = metrics_service.aggregate(experiment.runs)
    recommendation = recommendation_service.recommend(metrics, experiment.recommendation_weights)
    recommended_model = db.get(LLMModel, uuid.UUID(recommendation["recommended_model_id"]))
    assert recommended_model is not None
    assert recommended_model.display_name == "Pulse Balanced"
    simulator = db.scalar(select(Provider).where(Provider.key == "simulated"))
    assert simulator is not None
    assert simulator.supports_model_sync is False


def test_demo_user_can_be_resolved_without_public_credentials(db) -> None:
    seed_demo(db)

    user = auth_service.demo_user(db)

    assert user.email == "demo@evalforge.dev"
    assert user.is_demo is True
    assert user.is_active is True


def test_public_registration_endpoint_is_disabled() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/auth/register",
        json={
            "email": "blocked@example.com",
            "password": "BlockedPassword123!",
            "display_name": "Blocked",
            "language": "en",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Public registration is disabled"
