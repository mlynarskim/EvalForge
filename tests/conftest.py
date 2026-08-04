from __future__ import annotations

import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:////tmp/evalforge_test.db"
os.environ["SESSION_SECRET"] = "test-session-secret-with-at-least-thirty-two-characters"
os.environ["DEMO_MODE"] = "true"

import pytest

from app.database import Base, SessionLocal, engine


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session
