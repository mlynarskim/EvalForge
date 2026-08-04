from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Role(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(2), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    memberships: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Workspace(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    default_currency: Mapped[str] = mapped_column(String(3), default="PLN")
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)

    members: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspaceMember(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.MEMBER)

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Provider(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "providers"

    key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str | None] = mapped_column(String(500))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_model_sync: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderCredential(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (UniqueConstraint("workspace_id", "provider_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id"), index=True)
    encrypted_api_key: Mapped[bytes | None] = mapped_column(LargeBinary)
    encrypted_base_url: Mapped[bytes | None] = mapped_column(LargeBinary)
    masked_value: Mapped[str] = mapped_column(String(32), default="")
    connection_status: Mapped[str] = mapped_column(String(32), default="not_configured")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    provider: Mapped[Provider] = relationship()


class LLMModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "llm_models"
    __table_args__ = (
        UniqueConstraint("workspace_id", "provider_id", "model_id"),
        Index("ix_llm_models_provider_status", "provider_id", "status"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id"), index=True)
    model_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    family: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50), default="general")
    status: Mapped[str] = mapped_column(String(30), default="active")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_json_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_json_schema: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_reasoning: Mapped[bool] = mapped_column(Boolean, default=False)
    context_window: Mapped[int | None] = mapped_column(Integer)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    provider: Mapped[Provider] = relationship()
    prices: Mapped[list[ModelPricing]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )


class ModelPricing(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_pricing"
    __table_args__ = (Index("ix_model_pricing_effective", "model_id", "effective_from"),)

    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("llm_models.id"), index=True)
    input_price_per_million: Mapped[float | None] = mapped_column(Float)
    output_price_per_million: Mapped[float | None] = mapped_column(Float)
    cached_input_price_per_million: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str | None] = mapped_column(String(500))
    note: Mapped[str | None] = mapped_column(Text)

    model: Mapped[LLMModel] = relationship(back_populates="prices")


class Prompt(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompts"
    __table_args__ = (Index("ix_prompts_workspace_archived", "workspace_id", "is_archived"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    versions: Mapped[list[PromptVersion]] = relationship(
        back_populates="prompt", cascade="all, delete-orphan", order_by="PromptVersion.version"
    )


class PromptVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_id", "version"),)

    prompt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompts.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    user_template: Mapped[str] = mapped_column(Text)
    variables: Mapped[list[str]] = mapped_column(JSON, default=list)
    response_format: Mapped[str] = mapped_column(String(30), default="text")
    json_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    change_note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    prompt: Mapped[Prompt] = relationship(back_populates="versions")


class Dataset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "datasets"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    versions: Mapped[list[DatasetVersion]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", order_by="DatasetVersion.version"
    )


class DatasetVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)

    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    required_variables: Mapped[list[str]] = mapped_column(JSON, default=list)
    change_note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    dataset: Mapped[Dataset] = relationship(back_populates="versions")
    test_cases: Mapped[list[TestCase]] = relationship(
        back_populates="dataset_version", cascade="all, delete-orphan"
    )


class TestCase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_cases"
    __table_args__ = (
        Index("ix_test_cases_dataset_difficulty", "dataset_version_id", "difficulty"),
    )

    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_versions.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    expected_output: Mapped[Any | None] = mapped_column(JSON)
    expected_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    reference_context: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")

    dataset_version: Mapped[DatasetVersion] = relationship(back_populates="test_cases")


class Experiment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "experiments"
    __table_args__ = (Index("ix_experiments_workspace_status", "workspace_id", "status"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus), default=ExperimentStatus.DRAFT
    )
    prompt_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompt_versions.id"))
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_versions.id"))
    baseline_experiment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("experiments.id"))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evaluator_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recommendation_weights: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    regression_thresholds: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    maximum_budget: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    models: Mapped[list[ExperimentModel]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )
    runs: Mapped[list[ExperimentRun]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )


class ExperimentModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "experiment_models"
    __table_args__ = (UniqueConstraint("experiment_id", "model_id"),)

    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("llm_models.id"), index=True)
    pricing_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    normalized_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    experiment: Mapped[Experiment] = relationship(back_populates="models")
    model: Mapped[LLMModel] = relationship()


class ExperimentRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "experiment_runs"
    __table_args__ = (
        Index("ix_runs_experiment_status", "experiment_id", "status"),
        Index("ix_runs_model_test_case", "model_id", "test_case_id"),
    )

    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("llm_models.id"), index=True)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id"), index=True)
    repetition: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    provider_key: Mapped[str] = mapped_column(String(40))
    provider_model_id: Mapped[str] = mapped_column(String(255))
    prompt_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    dataset_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    parameter_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    pricing_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    raw_response: Mapped[str | None] = mapped_column(Text)
    parsed_response: Mapped[Any | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[float | None] = mapped_column(Float)
    time_to_first_token_ms: Mapped[float | None] = mapped_column(Float)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    input_cost: Mapped[float] = mapped_column(Float, default=0.0)
    output_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_category: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)

    experiment: Mapped[Experiment] = relationship(back_populates="runs")
    evaluations: Mapped[list[EvaluationResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class EvaluationResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (Index("ix_evaluations_run_evaluator", "run_id", "evaluator"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    evaluator: Mapped[str] = mapped_column(String(60))
    score: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_automated_judge: Mapped[bool] = mapped_column(Boolean, default=False)

    run: Mapped[ExperimentRun] = relationship(back_populates="evaluations")


class ManualReview(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "manual_reviews"
    __table_args__ = (UniqueConstraint("run_id", "reviewer_id"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    stars: Mapped[int | None] = mapped_column(Integer)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    is_useful: Mapped[bool | None] = mapped_column(Boolean)
    comment: Mapped[str | None] = mapped_column(Text)
    error_labels: Mapped[list[str]] = mapped_column(JSON, default=list)


class RegressionResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "regression_results"

    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    baseline_experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"))
    status: Mapped[str] = mapped_column(String(30))
    metric_changes: Mapped[dict[str, Any]] = mapped_column(JSON)


class Report(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    generated_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    format: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3))
    file_path: Mapped[str] = mapped_column(String(1000))
    checksum: Mapped[str] = mapped_column(String(128))


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_workspace_created", "workspace_id", "created_at"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
