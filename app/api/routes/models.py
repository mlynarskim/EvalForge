from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import WorkspaceContext, require_roles, workspace_context
from app.database import get_db
from app.models import LLMModel, ModelPricing, Provider
from app.models.entities import Role
from app.schemas.provider import ManualModelCreate, PricingCreate
from app.services.audit_service import audit

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
def list_models(
    provider_id: uuid.UUID | None = None,
    active: bool | None = None,
    context: WorkspaceContext = Depends(workspace_context),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    query = (
        select(LLMModel)
        .options(selectinload(LLMModel.provider), selectinload(LLMModel.prices))
        .where(LLMModel.workspace_id == context.workspace.id)
    )
    if provider_id:
        query = query.where(LLMModel.provider_id == provider_id)
    if active is not None:
        query = query.where(LLMModel.is_active == active)
    models = db.scalars(query.order_by(LLMModel.display_name)).all()
    return [
        {
            "id": model.id,
            "model_id": model.model_id,
            "display_name": model.display_name,
            "provider": model.provider.display_name,
            "provider_key": model.provider.key,
            "status": model.status,
            "is_active": model.is_active,
            "capabilities": {
                "streaming": model.supports_streaming,
                "json": model.supports_json_mode,
                "json_schema": model.supports_json_schema,
                "tools": model.supports_tools,
                "vision": model.supports_vision,
                "reasoning": model.supports_reasoning,
            },
            "latest_pricing": (
                {
                    "input": model.prices[-1].input_price_per_million,
                    "output": model.prices[-1].output_price_per_million,
                    "currency": model.prices[-1].currency,
                }
                if model.prices
                else None
            ),
            "last_synced_at": model.last_synced_at,
        }
        for model in models
    ]


@router.post("", status_code=201)
def add_manual_model(
    payload: ManualModelCreate,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    provider = db.get(Provider, payload.provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    model = LLMModel(
        workspace_id=context.workspace.id,
        provider_id=payload.provider_id,
        is_manual=True,
        **payload.model_dump(exclude={"provider_id"}),
    )
    db.add(model)
    db.flush()
    audit(db, context.workspace.id, context.user.id, "model.created", "model", model.id)
    db.commit()
    return {"id": model.id, "model_id": model.model_id}


@router.patch("/{model_id}/active")
def set_model_active(
    model_id: uuid.UUID,
    active: bool,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    model = db.get(LLMModel, model_id)
    if not model or model.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Model not found")
    model.is_active = active
    db.commit()
    return {"is_active": active}


@router.post("/{model_id}/pricing", status_code=201)
def add_pricing(
    model_id: uuid.UUID,
    payload: PricingCreate,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    model = db.get(LLMModel, model_id)
    if not model or model.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Model not found")
    price = ModelPricing(model_id=model.id, **payload.model_dump())
    db.add(price)
    db.flush()
    audit(db, context.workspace.id, context.user.id, "pricing.created", "model", model.id)
    db.commit()
    return {"id": price.id, "effective_from": price.effective_from}
