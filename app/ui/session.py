from nicegui import app, ui

from app.database import SessionLocal
from app.services.auth_service import AuthenticationError, auth_service


def enter_demo() -> None:
    """Start a read only demo session without exposing shared credentials."""
    try:
        with SessionLocal() as db:
            user = auth_service.demo_user(db)
            session_data = {"user_id": str(user.id), "language": user.language}
        app.storage.user.update(session_data)
        ui.navigate.to("/dashboard")
    except AuthenticationError as exc:
        ui.notify(str(exc), type="negative")
