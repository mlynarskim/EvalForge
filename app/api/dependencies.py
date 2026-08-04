from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Workspace, WorkspaceMember
from app.models.entities import Role
from app.services.auth_service import AuthenticationError, auth_service

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    try:
        return auth_service.resolve_token(db, credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@dataclass(slots=True)
class WorkspaceContext:
    user: User
    workspace: Workspace
    role: Role


def workspace_context(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> WorkspaceContext:
    membership = db.scalar(
        select(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(WorkspaceMember.created_at)
        .limit(1)
    )
    if not membership:
        raise HTTPException(status_code=403, detail="No workspace membership")
    workspace = db.get(Workspace, membership.workspace_id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Workspace is unavailable")
    return WorkspaceContext(user=user, workspace=workspace, role=membership.role)


def require_roles(*roles: Role) -> Callable[[WorkspaceContext], WorkspaceContext]:
    def dependency(context: WorkspaceContext = Depends(workspace_context)) -> WorkspaceContext:
        if context.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient workspace permission")
        return context

    return dependency
