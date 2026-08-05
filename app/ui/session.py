from nicegui import app, ui

from app.database import SessionLocal
from app.services.auth_service import AuthenticationError, auth_service
from app.ui.i18n import t


def enter_demo() -> None:
    """Start a browser session for the seeded demonstration account."""
    try:
        with SessionLocal() as db:
            user = auth_service.demo_user(db)
            user_id = str(user.id)
            language = user.language
        app.storage.user.update({"user_id": user_id, "language": language})
        ui.navigate.to("/dashboard")
    except AuthenticationError:
        ui.notify(t("demo_unavailable"), type="negative")
