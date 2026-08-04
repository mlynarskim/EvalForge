from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings, settings


class EncryptionError(ValueError):
    """Raised when encrypted configuration cannot be decrypted safely."""


class EncryptionService:
    """Encrypt provider secrets at rest using Fernet authenticated encryption."""

    def __init__(self, config: Settings = settings) -> None:
        if config.is_production and not config.encryption_key:
            raise RuntimeError("ENCRYPTION_KEY is required in production")
        key = config.encryption_key
        if not key:
            digest = hashlib.sha256(config.session_secret.encode()).digest()
            key = base64.urlsafe_b64encode(digest).decode()
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise RuntimeError("ENCRYPTION_KEY must be a valid Fernet key") from exc

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        try:
            return self._fernet.decrypt(ciphertext).decode()
        except InvalidToken as exc:
            raise EncryptionError("The encrypted secret cannot be decrypted") from exc

    @staticmethod
    def mask(secret: str) -> str:
        if len(secret) <= 8:
            return "••••••••"
        return f"{secret[:3]}••••••{secret[-4:]}"
