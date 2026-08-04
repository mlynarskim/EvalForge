from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CredentialUpsert(BaseModel):
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    base_url: str | None = Field(default=None, max_length=500)


class ProviderResponse(ORMModel):
    id: uuid.UUID
    key: str
    display_name: str
    is_enabled: bool
    connection_status: str = "not_configured"
    masked_value: str = ""


class ManualModelCreate(BaseModel):
    provider_id: uuid.UUID
    model_id: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    family: str | None = None
    category: str = "general"
    supports_streaming: bool = False
    supports_json_mode: bool = False
    supports_json_schema: bool = False
    supports_tools: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    context_window: int | None = None
    max_output_tokens: int | None = None


class PricingCreate(BaseModel):
    input_price_per_million: float | None = Field(default=None, ge=0)
    output_price_per_million: float | None = Field(default=None, ge=0)
    cached_input_price_per_million: float | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", pattern="^(USD|EUR|PLN)$")
    source: str | None = None
    note: str | None = None
