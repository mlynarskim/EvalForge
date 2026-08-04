from __future__ import annotations

import uuid

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, Workspace, WorkspaceMember
from app.models.entities import Role


class AuthenticationError(ValueError):
    pass


class AuthService:
    """Local password authentication and signed session token management."""

    def __init__(self) -> None:
        self.password_hash = PasswordHash.recommended()
        self.serializer = URLSafeTimedSerializer(settings.session_secret, salt="evalforge-auth")

    def register(
        self, db: Session, email: str, password: str, display_name: str, language: str = "en"
    ) -> tuple[User, Workspace]:
        normalized_email = email.strip().lower()
        if db.scalar(select(User).where(User.email == normalized_email)):
            raise AuthenticationError("An account with this email already exists")
        user = User(
            email=normalized_email,
            password_hash=self.password_hash.hash(password),
            display_name=display_name.strip(),
            language=language,
        )
        db.add(user)
        db.flush()
        workspace = Workspace(
            name=f"{display_name.strip()}'s workspace",
            slug=f"workspace-{str(user.id)[:8]}",
            owner_id=user.id,
            default_currency=settings.default_currency,
        )
        db.add(workspace)
        db.flush()
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=Role.ADMIN))
        db.commit()
        return user, workspace

    def authenticate(self, db: Session, email: str, password: str) -> User:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if (
            not user
            or not user.is_active
            or not self.password_hash.verify(password, user.password_hash)
        ):
            raise AuthenticationError("Invalid email or password")
        return user

    def create_token(self, user: User) -> str:
        return self.serializer.dumps({"user_id": str(user.id)})

    def resolve_token(self, db: Session, token: str, max_age: int = 86_400) -> User:
        try:
            data = self.serializer.loads(token, max_age=max_age)
            user_id = uuid.UUID(data["user_id"])
        except (BadSignature, SignatureExpired, KeyError, ValueError) as exc:
            raise AuthenticationError("Invalid or expired access token") from exc
        user = db.get(User, user_id)
        if not user or not user.is_active:
            raise AuthenticationError("Account is unavailable")
        return user


auth_service = AuthService()
