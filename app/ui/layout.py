from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import app, ui
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import User, Workspace, WorkspaceMember
from app.ui.i18n import t
from app.ui.theme import apply_theme

NAV_ITEMS = [
    ("dashboard", "dashboard", "space_dashboard"),
    ("experiments", "experiments", "science"),
    ("prompts", "prompts", "terminal"),
    ("datasets", "datasets", "dataset"),
    ("models", "models", "memory"),
    ("providers", "providers", "hub"),
    ("reports", "reports", "description"),
    ("settings", "settings", "settings"),
]


def signed_in_user() -> User | None:
    value = app.storage.user.get("user_id")
    if not value:
        return None
    try:
        user_id = uuid.UUID(value)
    except ValueError:
        app.storage.user.clear()
        return None
    with SessionLocal() as db:
        return db.get(User, user_id)


def require_user() -> User | None:
    user = signed_in_user()
    if not user:
        ui.navigate.to("/login")
    return user


def workspace_for_user(user_id: uuid.UUID) -> Workspace | None:
    with SessionLocal() as db:
        membership = db.scalar(
            select(WorkspaceMember).where(WorkspaceMember.user_id == user_id).limit(1)
        )
        return db.get(Workspace, membership.workspace_id) if membership else None


@contextmanager
def page_frame(title_key: str) -> Iterator[User]:
    apply_theme()
    user = require_user()
    if not user:
        return
    dark = ui.dark_mode(value=bool(app.storage.user.get("dark", False)))
    with ui.left_drawer(value=True).classes("ef-nav").props("width=250 breakpoint=900") as drawer:
        with ui.row().classes("items-center gap-3 px-4 py-5"):
            ui.label("EF").classes("ef-brand-mark")
            with ui.column().classes("gap-0"):
                ui.label("EvalForge").classes("text-lg font-bold")
                ui.label(t("subtitle")).classes("text-xs ef-muted")
        ui.separator()
        with ui.column().classes("w-full py-3 gap-0"):
            for path, label, icon in NAV_ITEMS:
                with ui.item(on_click=lambda target=path: ui.navigate.to(f"/{target}")):
                    with ui.item_section().props("avatar"):
                        ui.icon(icon)
                    with ui.item_section():
                        ui.item_label(t(label))
        ui.space()
        with ui.row().classes("items-center px-4 py-4"):
            ui.avatar(
                user.display_name[:1].upper(), color="primary", text_color="white", size="36px"
            )
            with ui.column().classes("gap-0"):
                ui.label(user.display_name).classes("text-sm font-medium")
                ui.label(user.email).classes("text-xs ef-muted")
    with ui.header().classes("ef-header border-b h-16"):
        ui.button(icon="menu", on_click=drawer.toggle).props("flat round aria-label=Menu")
        ui.label(t(title_key)).classes("text-lg font-semibold")
        ui.space()

        def toggle_dark() -> None:
            dark.toggle()
            app.storage.user["dark"] = dark.value

        ui.button(icon="dark_mode", on_click=toggle_dark).props("flat round aria-label=Theme")
        ui.badge("DEMO", color="amber") if user.is_demo else None
        ui.button(icon="logout", on_click=logout).props(f"flat round aria-label={t('logout')}")
    with ui.column().classes("ef-page w-full gap-6"):
        if settings.showcase_mode:
            with ui.card().classes("ef-demo w-full p-4 shadow-none"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("visibility", color="amber")
                    ui.label(t("showcase_banner")).classes("font-medium")
        with ui.row().classes("w-full items-center"):
            with ui.column().classes("gap-0"):
                ui.label(t(title_key)).classes("text-3xl font-bold tracking-tight")
                ui.label(t("subtitle")).classes("ef-muted")
        yield user


def logout() -> None:
    language = app.storage.user.get("language", settings.default_language)
    dark = app.storage.user.get("dark", False)
    app.storage.user.clear()
    app.storage.user.update({"language": language, "dark": dark})
    ui.navigate.to("/login")
