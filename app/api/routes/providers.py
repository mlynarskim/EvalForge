from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import WorkspaceContext, require_roles, workspace_context
from app.database import get_db
from app.models import Provider, ProviderCredential
from app.models.entities import Role, utcnow
from app.providers import ProviderError, ProviderRegistry
from app.schemas.provider import CredentialUpsert
from app.services.audit_service import audit
from app.services.encryption_service import EncryptionService
from app.services.model_sync_service import model_sync_service

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("")
def list_providers(
    context: WorkspaceContext = Depends(workspace_context), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    credentials = {
        item.provider_id: item
        for item in db.scalars(
            select(ProviderCredential).where(
                ProviderCredential.workspace_id == context.workspace.id
            )
        )
    }
    result: list[dict[str, object]] = []
    for provider in db.scalars(select(Provider).order_by(Provider.display_name)):
        credential = credentials.get(provider.id)
        result.append(
            {
                "id": provider.id,
                "key": provider.key,
                "display_name": provider.display_name,
                "is_enabled": provider.is_enabled,
                "connection_status": credential.connection_status
                if credential
                else "not_configured",
                "masked_value": credential.masked_value if credential else "",
            }
        )
    return result


@router.put("/{provider_id}/credential")
def save_credential(
    provider_id: uuid.UUID,
    payload: CredentialUpsert,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    provider = db.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == context.workspace.id,
            ProviderCredential.provider_id == provider_id,
        )
    ) or ProviderCredential(workspace_id=context.workspace.id, provider_id=provider_id)
    encryption = EncryptionService()
    if payload.api_key is not None:
        credential.encrypted_api_key = encryption.encrypt(payload.api_key)
        credential.masked_value = encryption.mask(payload.api_key)
    if payload.base_url is not None:
        credential.encrypted_base_url = encryption.encrypt(payload.base_url)
    credential.connection_status = "not_checked"
    db.add(credential)
    audit(
        db,
        context.workspace.id,
        context.user.id,
        "provider.credential_saved",
        "provider",
        provider_id,
    )
    db.commit()
    return {"status": credential.connection_status, "masked_value": credential.masked_value}


@router.delete("/{provider_id}/credential", status_code=204)
def delete_credential(
    provider_id: uuid.UUID,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == context.workspace.id,
            ProviderCredential.provider_id == provider_id,
        )
    )
    if credential:
        db.delete(credential)
        audit(
            db,
            context.workspace.id,
            context.user.id,
            "provider.credential_deleted",
            "provider",
            provider_id,
        )
        db.commit()


@router.post("/{provider_id}/validate")
async def validate_credential(
    provider_id: uuid.UUID,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    provider = db.get(Provider, provider_id)
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == context.workspace.id,
            ProviderCredential.provider_id == provider_id,
        )
    )
    if not provider or not credential:
        raise HTTPException(status_code=404, detail="Provider credential not found")
    encryption = EncryptionService()
    adapter = ProviderRegistry.create(
        provider.key,
        encryption.decrypt(credential.encrypted_api_key) if credential.encrypted_api_key else None,
        encryption.decrypt(credential.encrypted_base_url)
        if credential.encrypted_base_url
        else None,
    )
    try:
        await adapter.validate_credentials()
        credential.connection_status = "connected"
    except ProviderError as exc:
        credential.connection_status = exc.category
    credential.last_checked_at = utcnow()
    db.commit()
    return {"status": credential.connection_status}


@router.post("/{provider_id}/sync")
async def sync_models(
    provider_id: uuid.UUID,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    provider = db.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    try:
        result = await model_sync_service.sync(db, context.workspace.id, provider)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    audit(
        db,
        context.workspace.id,
        context.user.id,
        "models.synchronized",
        "provider",
        provider_id,
        result,
    )
    db.commit()
    return result
