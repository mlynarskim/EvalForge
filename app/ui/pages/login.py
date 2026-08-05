from nicegui import app, ui

from app.config import settings
from app.database import SessionLocal
from app.services.auth_service import AuthenticationError, auth_service
from app.ui.i18n import t
from app.ui.session import enter_demo
from app.ui.theme import apply_theme


def register() -> None:
    @ui.page("/login")
    def login_page() -> None:
        apply_theme()
        if app.storage.user.get("user_id"):
            ui.navigate.to("/dashboard")
            return
        ui.dark_mode(value=bool(app.storage.user.get("dark", False)))
        with ui.row().classes("absolute top-5 right-5 items-center"):
            language = ui.select(
                {"en": "English", "pl": "Polski"},
                value=app.storage.user.get("language", settings.default_language),
            ).props("dense outlined options-dense")

            def change_language() -> None:
                app.storage.user["language"] = language.value
                ui.navigate.reload()

            language.on_value_change(change_language)
        with ui.column().classes("w-full min-h-screen items-center justify-center px-4"):
            with ui.row().classes("items-center gap-3 mb-3"):
                ui.label("EF").classes("ef-brand-mark")
                ui.label("EvalForge").classes("text-3xl font-bold")
            ui.label(t("subtitle")).classes("ef-muted text-center mb-6")
            with ui.card().classes("ef-card w-full max-w-md p-2"):
                if settings.demo_mode:
                    with ui.card().classes("ef-demo w-full p-4 shadow-none"):
                        ui.label(t("demo_credentials")).classes("font-semibold")
                        ui.label(t("demo_access_help")).classes("text-sm ef-muted")
                        ui.button(
                            t("enter_demo"),
                            icon="play_arrow",
                            on_click=enter_demo,
                        ).props("unelevated no-caps").classes("w-full mt-2")
                        if settings.showcase_mode:
                            ui.label(t("showcase_read_only")).classes("text-xs mt-1")
                if settings.showcase_mode:
                    ui.button(
                        t("back_to_home"),
                        icon="arrow_back",
                        on_click=lambda: ui.navigate.to("/welcome"),
                    ).props("flat no-caps").classes("w-full mt-2")
                    return
                tabs = ui.tabs().classes("w-full")
                register_tab = None
                with tabs:
                    sign_in_tab = ui.tab(t("login"), icon="login")
                    if settings.registration_enabled and not settings.showcase_mode:
                        register_tab = ui.tab(t("register"), icon="person_add")
                with ui.tab_panels(tabs, value=sign_in_tab).classes("w-full"):
                    with ui.tab_panel(sign_in_tab):
                        email = ui.input(t("email")).props("outlined type=email").classes("w-full")
                        password = (
                            ui.input(t("password"), password=True, password_toggle_button=True)
                            .props("outlined")
                            .classes("w-full")
                        )

                        def submit_login() -> None:
                            try:
                                with SessionLocal() as db:
                                    user = auth_service.authenticate(
                                        db, email.value, password.value
                                    )
                                app.storage.user.update(
                                    {"user_id": str(user.id), "language": user.language}
                                )
                                ui.navigate.to("/dashboard")
                            except AuthenticationError:
                                ui.notify(t("invalid_login"), type="negative")

                        ui.button(t("login"), icon="login", on_click=submit_login).props(
                            "unelevated"
                        ).classes("w-full mt-3")
                    if register_tab is not None:
                        with ui.tab_panel(register_tab):
                            display_name = ui.input(t("name")).props("outlined").classes("w-full")
                            new_email = (
                                ui.input(t("email")).props("outlined type=email").classes("w-full")
                            )
                            new_password = (
                                ui.input(t("password"), password=True, password_toggle_button=True)
                                .props("outlined")
                                .classes("w-full")
                            )

                            def submit_registration() -> None:
                                try:
                                    with SessionLocal() as db:
                                        user, _ = auth_service.register(
                                            db,
                                            new_email.value,
                                            new_password.value,
                                            display_name.value,
                                            app.storage.user.get("language", "en"),
                                        )
                                    app.storage.user["user_id"] = str(user.id)
                                    ui.notify(t("account_created"), type="positive")
                                    ui.navigate.to("/dashboard")
                                except (AuthenticationError, ValueError) as exc:
                                    ui.notify(str(exc), type="negative")

                            ui.button(
                                t("register"), icon="person_add", on_click=submit_registration
                            ).props("unelevated").classes("w-full mt-3")
