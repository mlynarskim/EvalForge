from nicegui import app, ui

from app.config import settings
from app.database import SessionLocal
from app.models import User, Workspace
from app.ui.i18n import t
from app.ui.layout import page_frame, require_user, workspace_for_user


def register() -> None:
    @ui.page("/settings")
    def settings_page() -> None:
        user = require_user()
        if not user:
            return
        workspace = workspace_for_user(user.id)
        if workspace is None:
            return
        with page_frame("settings"):
            with ui.card().classes("ef-card p-5 w-full max-w-2xl"):
                ui.label(t("language")).classes("text-lg font-semibold")
                language = (
                    ui.select(
                        {"en": "English", "pl": "Polski"},
                        value=app.storage.user.get("language", user.language),
                        label=t("language"),
                    )
                    .props("outlined")
                    .classes("w-full")
                )
                currency = (
                    ui.select(
                        {"PLN": "PLN", "USD": "USD", "EUR": "EUR"},
                        value=workspace.default_currency,
                        label=t("currency"),
                    )
                    .props("outlined")
                    .classes("w-full")
                )
                if settings.showcase_mode:
                    currency.props("disable")

                def save() -> None:
                    if not settings.showcase_mode:
                        with SessionLocal() as db:
                            db_user = db.get(User, user.id)
                            db_workspace = db.get(Workspace, workspace.id)
                            if db_user is None or db_workspace is None:
                                ui.notify("Settings are unavailable", type="negative")
                                return
                            db_user.language = language.value
                            db_workspace.default_currency = currency.value
                            db.commit()
                    app.storage.user["language"] = language.value
                    ui.notify(t("saved"), type="positive")
                    ui.navigate.reload()

                ui.button(t("save"), icon="save", on_click=save).props("unelevated")
