"""SQLAlchemy ORM models mirroring the Supabase schema."""
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Pipeline Runs ─────────────────────────────────────────────────────────────

class PipelineRun(Base):
    """Tracks the state of every pipeline execution."""

    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    current_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    stage_progress: Mapped[int] = mapped_column(Integer, default=0)
    jobs_scraped: Mapped[int] = mapped_column(Integer, default=0)
    jobs_scored: Mapped[int] = mapped_column(Integer, default=0)
    jobs_selected: Mapped[int] = mapped_column(Integer, default=0)
    applications_submitted: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    stage_results: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    llm_calls: Mapped[list["LLMCall"]] = relationship(back_populates="pipeline_run")


# ── User Profile ──────────────────────────────────────────────────────────────

class UserProfile(Base):
    """Stores the active user's parsed resume data."""

    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    profile_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    resume_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


# ── Job Listings ──────────────────────────────────────────────────────────────

class JobListing(Base):
    """Scraped job listings, deduplicated by job_id."""

    __tablename__ = "job_listings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    job_type: Mapped[str | None] = mapped_column(String, nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_period: Mapped[str | None] = mapped_column(String, nullable=True)
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    requirements: Mapped[list] = mapped_column(JSONB, default=list)
    posted_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    embedding: Mapped["JobEmbedding | None"] = relationship(
        back_populates="job", uselist=False
    )


# ── Job Embeddings (pgvector) ─────────────────────────────────────────────────

class JobEmbedding(Base):
    """nomic-embed-text 768-dim vectors for semantic job search (replaces ChromaDB)."""

    __tablename__ = "job_embeddings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        String, ForeignKey("job_listings.job_id", ondelete="CASCADE"), unique=True, nullable=False
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    job: Mapped["JobListing"] = relationship(back_populates="embedding")


# ── Custom Statuses ───────────────────────────────────────────────────────────

class CustomStatus(Base):
    """User-defined application status labels."""

    __tablename__ = "custom_statuses"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String, default="#6B7280")
    icon: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    applications: Mapped[list["Application"]] = relationship(back_populates="custom_status")


# ── Applications ──────────────────────────────────────────────────────────────

class Application(Base):
    """Tracked job applications (saves, hides, external, pipeline-submitted)."""

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    job_title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    current_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    custom_status_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("custom_statuses.id"), nullable=True
    )
    is_bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bookmark_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    external_application_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timeline_notes: Mapped[list] = mapped_column(JSONB, default=list)
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    custom_status: Mapped["CustomStatus | None"] = relationship(back_populates="applications")
    interviews: Mapped[list["Interview"]] = relationship(back_populates="application")


# ── Interviews ────────────────────────────────────────────────────────────────

class Interview(Base):
    """Interview rounds linked to an application."""

    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    application: Mapped["Application"] = relationship(back_populates="interviews")


# ── LLM Calls (cost tracking) ─────────────────────────────────────────────────

class LLMCall(Base):
    """Every LLM API call for cost tracking and auditing."""

    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    task_type: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    pipeline_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("pipeline_runs.run_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    pipeline_run: Mapped["PipelineRun | None"] = relationship(back_populates="llm_calls")


# ── User Settings ─────────────────────────────────────────────────────────────

class UserSettings(Base):
    """Single-row table for persisted user settings (replaces JSON file)."""

    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    settings_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
