from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LLMModel, Provider, ProviderCredential
from app.models.entities import utcnow
from app.providers import ProviderRegistry
from app.services.encryption_service import EncryptionService


class ModelSyncService:
    """Synchronize provider models while retaining historical registry entries."""

    async def sync(
        self, db: Session, workspace_id: uuid.UUID, provider: Provider
    ) -> dict[str, int]:
        credential = db.scalar(
            select(ProviderCredential).where(
                ProviderCredential.workspace_id == workspace_id,
                ProviderCredential.provider_id == provider.id,
            )
        )
        encryption = EncryptionService()
        api_key = (
            encryption.decrypt(credential.encrypted_api_key)
            if credential and credential.encrypted_api_key
            else None
        )
        base_url = (
            encryption.decrypt(credential.encrypted_base_url)
            if credential and credential.encrypted_base_url
            else provider.base_url
        )
        adapter = ProviderRegistry.create(provider.key, api_key, base_url)
        remote_models = await adapter.list_models()
        remote_ids = {item.model_id for item in remote_models}
        existing = {
            item.model_id: item
            for item in db.scalars(
                select(LLMModel).where(
                    LLMModel.workspace_id == workspace_id, LLMModel.provider_id == provider.id
                )
            )
        }
        created = updated = 0
        now = utcnow()
        for info in remote_models:
            model = existing.get(info.model_id)
            if model:
                model.is_active = True
                model.last_synced_at = now
                model.context_window = info.context_window or model.context_window
                model.max_output_tokens = info.max_output_tokens or model.max_output_tokens
                updated += 1
            else:
                db.add(
                    LLMModel(
                        workspace_id=workspace_id,
                        provider_id=provider.id,
                        model_id=info.model_id,
                        display_name=info.display_name,
                        family=info.family,
                        context_window=info.context_window,
                        max_output_tokens=info.max_output_tokens,
                        supports_streaming="streaming" in info.capabilities,
                        supports_json_mode="json" in info.capabilities,
                        supports_tools="tools" in info.capabilities,
                        supports_vision="vision" in info.capabilities,
                        last_synced_at=now,
                    )
                )
                created += 1
        inactive = 0
        for model_id, model in existing.items():
            if model_id not in remote_ids and not model.is_manual:
                model.is_active = False
                inactive += 1
        if credential:
            credential.connection_status = "connected"
            credential.last_checked_at = now
        db.commit()
        return {"created": created, "updated": updated, "inactive": inactive}


model_sync_service = ModelSyncService()
