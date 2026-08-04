import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.api.dependencies import require_writable
from app.config import Settings, settings
from app.providers.base import TokenUsage
from app.services.encryption_service import EncryptionError, EncryptionService
from app.services.pricing_service import PricingService
from app.services.showcase_service import ShowcaseModeError, ensure_writable


def test_encryption_round_trip_and_masking() -> None:
    config = Settings(
        _env_file=None,
        app_env="test",
        session_secret="a-session-secret-longer-than-thirty-two-characters",
        encryption_key=Fernet.generate_key().decode(),
    )
    service = EncryptionService(config)
    encrypted = service.encrypt("sk-example-secret-value")
    assert b"sk-example-secret-value" not in encrypted
    assert service.decrypt(encrypted) == "sk-example-secret-value"
    assert service.mask("sk-example-secret-value") == "sk-••••••alue"


def test_decryption_rejects_tampered_ciphertext() -> None:
    config = Settings(
        _env_file=None,
        app_env="test",
        session_secret="a-session-secret-longer-than-thirty-two-characters",
        encryption_key=Fernet.generate_key().decode(),
    )
    service = EncryptionService(config)
    encrypted = service.encrypt("secret")
    try:
        service.decrypt(encrypted[:-2] + b"xx")
    except EncryptionError:
        pass
    else:
        raise AssertionError("Tampered data must not decrypt")


def test_pricing_uses_cached_tokens_and_currency_conversion() -> None:
    config = Settings(
        _env_file=None,
        app_env="test",
        session_secret="a-session-secret-longer-than-thirty-two-characters",
        usd_to_pln=4,
        eur_to_pln=4.4,
    )
    service = PricingService(config)
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=500_000, cached_tokens=200_000)
    cost = service.calculate(
        usage,
        {
            "input_price_per_million": 2,
            "output_price_per_million": 4,
            "cached_input_price_per_million": 1,
            "currency": "USD",
        },
        "PLN",
    )
    assert cost.input_cost == 7.2
    assert cost.output_cost == 8.0
    assert cost.total_cost == 15.2


def test_railway_postgres_url_uses_psycopg_driver() -> None:
    config = Settings(
        _env_file=None,
        app_env="test",
        session_secret="a-session-secret-longer-than-thirty-two-characters",
        database_url="postgresql://user:password@postgres:5432/evalforge",
    )
    assert config.database_url == "postgresql+psycopg://user:password@postgres:5432/evalforge"


def test_showcase_mode_rejects_service_and_api_mutations(monkeypatch) -> None:
    monkeypatch.setattr(settings, "showcase_mode", True)
    with pytest.raises(ShowcaseModeError, match="read only"):
        ensure_writable()
    with pytest.raises(HTTPException) as captured:
        require_writable()
    assert getattr(captured.value, "status_code", None) == 403
