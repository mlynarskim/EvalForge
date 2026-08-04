from sqlalchemy import func, select

from app.models import Experiment, User
from app.models import TestCase as DatasetCase
from app.services.auth_service import auth_service
from app.services.demo_service import seed_demo


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


def test_demo_seed_is_idempotent_and_contains_twenty_cases(db) -> None:
    seed_demo(db)
    seed_demo(db)
    assert db.scalar(select(func.count()).select_from(User)) == 1
    assert db.scalar(select(func.count()).select_from(DatasetCase)) == 20
    experiment = db.scalar(select(Experiment))
    assert experiment is not None
    assert experiment.is_demo is True
    assert experiment.total_cost == 0
