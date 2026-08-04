from __future__ import annotations

import uuid

from nicegui import ui
from sqlalchemy import select

from app.database import SessionLocal
from app.models import LLMModel, Provider, ProviderCredential
from app.providers import ProviderError, ProviderRegistry
from app.services.encryption_service import EncryptionService
from app.services.model_sync_service import model_sync_service
from app.ui.i18n import t
from app.ui.layout import page_frame, require_user, workspace_for_user


def register() -> None:
    @ui.page("/providers")
    def providers_page() -> None:
        user = require_user()
        if not user:
            return
        workspace = workspace_for_user(user.id)
        if not workspace:
            return
        with SessionLocal() as db:
            providers = list(db.scalars(select(Provider).order_by(Provider.display_name)))
            credentials = {
                item.provider_id: item
                for item in db.scalars(
                    select(ProviderCredential).where(
                        ProviderCredential.workspace_id == workspace.id
                    )
                )
            }
        with page_frame("providers"):
            ui.label(t("provider_help")).classes("ef-muted")
            with ui.element("div").classes("ef-card-grid"):
                for provider in providers:
                    credential = credentials.get(provider.id)
                    with ui.card().classes("ef-card p-5"):
                        with ui.row().classes("w-full items-center"):
                            ui.avatar(
                                provider.display_name[:1], color="primary", text_color="white"
                            )
                            with ui.column().classes("gap-0"):
                                ui.label(provider.display_name).classes("font-semibold text-lg")
                                ui.label(provider.key).classes("text-xs ef-muted")
                            ui.space()
                            status_value = (
                                credential.connection_status if credential else "not_configured"
                            )
                            ui.badge(
                                t(status_value),
                                color="green" if status_value == "connected" else "grey",
                            )
                        ui.label(credential.masked_value if credential else "••••••••").classes(
                            "font-mono text-sm my-3"
                        )

                        async def configure(provider_id: uuid.UUID = provider.id) -> None:
                            dialog = ui.dialog()
                            with dialog, ui.card().classes("w-[520px] max-w-full p-5"):
                                ui.label(t("api_key")).classes("text-xl font-semibold")
                                key = (
                                    ui.input(
                                        t("api_key"), password=True, password_toggle_button=True
                                    )
                                    .props("outlined")
                                    .classes("w-full")
                                )
                                url = ui.input(t("base_url")).props("outlined").classes("w-full")

                                def save() -> None:
                                    encryption = EncryptionService()
                                    with SessionLocal() as action_db:
                                        item = action_db.scalar(
                                            select(ProviderCredential).where(
                                                ProviderCredential.workspace_id == workspace.id,
                                                ProviderCredential.provider_id == provider_id,
                                            )
                                        ) or ProviderCredential(
                                            workspace_id=workspace.id, provider_id=provider_id
                                        )
                                        if key.value:
                                            item.encrypted_api_key = encryption.encrypt(key.value)
                                            item.masked_value = encryption.mask(key.value)
                                        if url.value:
                                            item.encrypted_base_url = encryption.encrypt(url.value)
                                        item.connection_status = "not_checked"
                                        action_db.add(item)
                                        action_db.commit()
                                    dialog.close()
                                    ui.notify(t("saved"), type="positive")
                                    ui.navigate.reload()

                                with ui.row().classes("justify-end w-full"):
                                    ui.button(t("cancel"), on_click=dialog.close).props("flat")
                                    ui.button(t("save"), on_click=save).props("unelevated")
                            dialog.open()

                        async def test(
                            provider_id: uuid.UUID = provider.id, provider_key: str = provider.key
                        ) -> None:
                            with SessionLocal() as action_db:
                                item = action_db.scalar(
                                    select(ProviderCredential).where(
                                        ProviderCredential.workspace_id == workspace.id,
                                        ProviderCredential.provider_id == provider_id,
                                    )
                                )
                                if not item:
                                    ui.notify(t("not_configured"), type="warning")
                                    return
                                encryption = EncryptionService()
                                adapter = ProviderRegistry.create(
                                    provider_key,
                                    encryption.decrypt(item.encrypted_api_key)
                                    if item.encrypted_api_key
                                    else None,
                                    encryption.decrypt(item.encrypted_base_url)
                                    if item.encrypted_base_url
                                    else None,
                                )
                                try:
                                    await adapter.validate_credentials()
                                    item.connection_status = "connected"
                                    ui.notify(t("connected"), type="positive")
                                except ProviderError as exc:
                                    item.connection_status = exc.category
                                    ui.notify(str(exc), type="negative")
                                action_db.commit()

                        async def sync(provider_id: uuid.UUID = provider.id) -> None:
                            with SessionLocal() as action_db:
                                current = action_db.get(Provider, provider_id)
                                if current is None:
                                    ui.notify("Provider not found", type="negative")
                                    return
                                try:
                                    result = await model_sync_service.sync(
                                        action_db, workspace.id, current
                                    )
                                    ui.notify(
                                        f"{result['created']} new, {result['updated']} updated",
                                        type="positive",
                                    )
                                except ProviderError as exc:
                                    ui.notify(str(exc), type="negative")

                        with ui.row().classes("w-full gap-2"):
                            ui.button(t("save"), icon="key", on_click=configure).props("outline")
                            ui.button(icon="wifi_tethering", on_click=test).props(
                                f"flat aria-label={t('test_connection')}"
                            )
                            ui.button(icon="sync", on_click=sync).props(
                                f"flat aria-label={t('sync')}"
                            )

    @ui.page("/models")
    def models_page() -> None:
        user = require_user()
        if not user:
            return
        workspace = workspace_for_user(user.id)
        if workspace is None:
            return
        with SessionLocal() as db:
            models = list(db.scalars(select(LLMModel).where(LLMModel.workspace_id == workspace.id)))
        with page_frame("models"):
            ui.label(t("model_registry_help")).classes("ef-muted")
            rows = [
                {
                    "name": item.display_name,
                    "model_id": item.model_id,
                    "status": item.status,
                    "active": item.is_active,
                    "synced": item.last_synced_at.strftime("%Y.%m.%d")
                    if item.last_synced_at
                    else "Manual",
                }
                for item in models
            ]
            columns = [
                {
                    "name": "name",
                    "label": t("name"),
                    "field": "name",
                    "sortable": True,
                    "align": "left",
                },
                {
                    "name": "model_id",
                    "label": "Model ID",
                    "field": "model_id",
                    "sortable": True,
                    "align": "left",
                },
                {"name": "status", "label": t("status"), "field": "status", "sortable": True},
                {"name": "active", "label": "Active", "field": "active", "sortable": True},
                {"name": "synced", "label": "Last sync", "field": "synced", "sortable": True},
            ]
            ui.table(columns=columns, rows=rows, row_key="model_id", pagination=20).classes(
                "ef-card w-full"
            ).props("flat bordered")
