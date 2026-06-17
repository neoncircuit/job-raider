"""Initial schema: all tables and pgvector index.

Revision ID: 0001
Revises:
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector — must be enabled in Supabase dashboard first
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("run_id", sa.String, unique=True, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("current_stage", sa.String, nullable=True),
        sa.Column("stage_progress", sa.Integer, server_default="0"),
        sa.Column("jobs_scraped", sa.Integer, server_default="0"),
        sa.Column("jobs_scored", sa.Integer, server_default="0"),
        sa.Column("jobs_selected", sa.Integer, server_default="0"),
        sa.Column("applications_submitted", sa.Integer, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("config", postgresql.JSONB, server_default="{}"),
        sa.Column("stage_results", postgresql.JSONB, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_pipeline_runs_run_id", "pipeline_runs", ["run_id"])

    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("profile_data", postgresql.JSONB, nullable=False),
        sa.Column("resume_path", sa.String, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "job_listings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("job_id", sa.String, unique=True, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("company", sa.String, nullable=False),
        sa.Column("location", sa.String, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("source_url", sa.String, nullable=True),
        sa.Column("is_remote", sa.Boolean, server_default="false"),
        sa.Column("job_type", sa.String, nullable=True),
        sa.Column("experience_level", sa.String, nullable=True),
        sa.Column("salary_min", sa.Numeric, nullable=True),
        sa.Column("salary_max", sa.Numeric, nullable=True),
        sa.Column("salary_currency", sa.String, nullable=True),
        sa.Column("salary_period", sa.String, nullable=True),
        sa.Column("skills", postgresql.JSONB, server_default="[]"),
        sa.Column("requirements", postgresql.JSONB, server_default="[]"),
        sa.Column("posted_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
    )
    op.create_index("ix_job_listings_job_id", "job_listings", ["job_id"])

    # pgvector: 768-dim for nomic-embed-text
    op.execute("""
        CREATE TABLE job_embeddings (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id      TEXT UNIQUE NOT NULL
                            REFERENCES job_listings(job_id) ON DELETE CASCADE,
            embedding   vector(768) NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """)
    op.execute(
        "CREATE INDEX ON job_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "custom_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("color", sa.String, server_default="#6B7280"),
        sa.Column("icon", sa.String, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("usage_count", sa.Integer, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("job_id", sa.String, nullable=False),
        sa.Column("job_title", sa.String, nullable=False),
        sa.Column("company", sa.String, nullable=False),
        sa.Column(
            "current_status", sa.String, nullable=False, server_default="pending"
        ),
        sa.Column(
            "custom_status_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("custom_statuses.id"),
            nullable=True,
        ),
        sa.Column("is_bookmarked", sa.Boolean, server_default="false"),
        sa.Column("is_hidden", sa.Boolean, server_default="false"),
        sa.Column("applied_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bookmark_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hidden_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_outcome", sa.String, nullable=True),
        sa.Column("external_application_details", postgresql.JSONB, nullable=True),
        sa.Column("timeline_notes", postgresql.JSONB, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_applications_job_id", "applications", ["job_id"])

    op.create_table(
        "interviews",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String, nullable=True),
        sa.Column("scheduled_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feedback", sa.Text, nullable=True),
        sa.Column("outcome", sa.String, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "llm_calls",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("task_type", sa.String, nullable=False),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("model_name", sa.String, nullable=False),
        sa.Column("prompt_tokens", sa.Integer, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, server_default="0"),
        sa.Column("total_tokens", sa.Integer, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), server_default="0"),
        sa.Column(
            "pipeline_run_id",
            sa.String,
            sa.ForeignKey("pipeline_runs.run_id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("settings_data", postgresql.JSONB, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
    op.drop_table("llm_calls")
    op.drop_table("interviews")
    op.drop_table("applications")
    op.drop_table("custom_statuses")
    op.execute("DROP TABLE IF EXISTS job_embeddings")
    op.drop_table("job_listings")
    op.drop_table("user_profiles")
    op.drop_table("pipeline_runs")
