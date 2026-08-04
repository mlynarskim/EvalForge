from __future__ import annotations

import difflib
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import WorkspaceContext, require_roles, workspace_context
from app.database import get_db
from app.models import Prompt, PromptVersion
from app.models.entities import Role
from app.schemas.prompt import PromptCreate, PromptVersionCreate
from app.services.audit_service import audit
from app.services.experiment_service import extract_variables

router = APIRouter(prefix="/prompts", tags=["prompts"])


def _serialize(prompt: Prompt) -> dict[str, object]:
    latest = prompt.versions[-1] if prompt.versions else None
    return {
        "id": prompt.id,
        "name": prompt.name,
        "description": prompt.description,
        "tags": prompt.tags,
        "is_archived": prompt.is_archived,
        "latest_version": latest.version if latest else None,
        "variables": latest.variables if latest else [],
        "updated_at": prompt.updated_at,
    }


@router.get("")
def list_prompts(
    archived: bool = False,
    context: WorkspaceContext = Depends(workspace_context),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    prompts = db.scalars(
        select(Prompt)
        .options(selectinload(Prompt.versions))
        .where(Prompt.workspace_id == context.workspace.id, Prompt.is_archived == archived)
        .order_by(Prompt.updated_at.desc())
    )
    return [_serialize(prompt) for prompt in prompts]


@router.post("", status_code=201)
def create_prompt(
    payload: PromptCreate,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    prompt = Prompt(
        workspace_id=context.workspace.id,
        created_by_id=context.user.id,
        name=payload.name,
        description=payload.description,
        tags=payload.tags,
    )
    db.add(prompt)
    db.flush()
    db.add(
        PromptVersion(
            prompt_id=prompt.id,
            version=1,
            system_prompt=payload.system_prompt,
            user_template=payload.user_template,
            variables=extract_variables(payload.user_template),
            response_format=payload.response_format,
            json_schema=payload.json_schema,
            created_by_id=context.user.id,
        )
    )
    audit(db, context.workspace.id, context.user.id, "prompt.created", "prompt", prompt.id)
    db.commit()
    return {"id": prompt.id, "version": 1}


@router.get("/{prompt_id}")
def get_prompt(
    prompt_id: uuid.UUID,
    context: WorkspaceContext = Depends(workspace_context),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    prompt = db.scalar(
        select(Prompt).options(selectinload(Prompt.versions)).where(Prompt.id == prompt_id)
    )
    if not prompt or prompt.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {**_serialize(prompt), "versions": prompt.versions}


@router.post("/{prompt_id}/versions", status_code=201)
def create_version(
    prompt_id: uuid.UUID,
    payload: PromptVersionCreate,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    prompt = db.get(Prompt, prompt_id)
    if not prompt or prompt.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Prompt not found")
    version_number = (
        int(
            db.scalar(
                select(func.max(PromptVersion.version)).where(PromptVersion.prompt_id == prompt.id)
            )
            or 0
        )
        + 1
    )
    version = PromptVersion(
        prompt_id=prompt.id,
        version=version_number,
        variables=extract_variables(payload.user_template),
        created_by_id=context.user.id,
        **payload.model_dump(),
    )
    db.add(version)
    audit(
        db,
        context.workspace.id,
        context.user.id,
        "prompt.version_created",
        "prompt",
        prompt.id,
        {"version": version_number},
    )
    db.commit()
    return {"id": version.id, "version": version_number}


@router.get("/{prompt_id}/compare")
def compare_versions(
    prompt_id: uuid.UUID,
    left: int,
    right: int,
    context: WorkspaceContext = Depends(workspace_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    prompt = db.get(Prompt, prompt_id)
    if not prompt or prompt.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Prompt not found")
    versions = {
        item.version: item
        for item in db.scalars(
            select(PromptVersion).where(
                PromptVersion.prompt_id == prompt_id, PromptVersion.version.in_([left, right])
            )
        )
    }
    if left not in versions or right not in versions:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    diff = difflib.unified_diff(
        versions[left].user_template.splitlines(),
        versions[right].user_template.splitlines(),
        fromfile=f"version {left}",
        tofile=f"version {right}",
        lineterm="",
    )
    return {"diff": "\n".join(diff)}


@router.patch("/{prompt_id}/archive")
def archive_prompt(
    prompt_id: uuid.UUID,
    archived: bool = True,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    prompt = db.get(Prompt, prompt_id)
    if not prompt or prompt.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt.is_archived = archived
    db.commit()
    return {"is_archived": archived}
