from __future__ import annotations

from app.config import settings


class ShowcaseModeError(PermissionError):
    pass


def ensure_writable() -> None:
    """Reject mutations when the application is exposed as a public showcase."""
    if settings.showcase_mode:
        raise ShowcaseModeError("The public showcase is read only")
