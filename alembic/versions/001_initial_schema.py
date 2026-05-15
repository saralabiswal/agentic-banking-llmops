"""Initial platform schema.

Author: Sarala Biswal
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Create initial platform tables."""
    op.create_table(
        "feature_store",
        sa.Column("customer_id", sa.String(length=64), primary_key=True),
        sa.Column("feature_name", sa.String(length=128), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("audit_id", sa.String(length=128), primary_key=True),
        sa.Column("trace_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=True, index=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "approval_queue",
        sa.Column("queue_id", sa.String(length=128), primary_key=True),
        sa.Column("trace_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("customer_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("proposed_action", sa.JSON(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
    )
    op.create_table(
        "experiments",
        sa.Column("experiment_id", sa.String(length=128), primary_key=True),
        sa.Column("scenario", sa.String(length=64), nullable=False, index=True),
        sa.Column("action_type", sa.String(length=64), nullable=False, index=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("winner_variant_id", sa.String(length=128), nullable=True),
        sa.Column("min_sample_size", sa.Integer(), nullable=False),
        sa.Column("confidence_threshold", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("concluded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "experiment_variants",
        sa.Column("variant_id", sa.String(length=128), primary_key=True),
        sa.Column("experiment_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "experiment_results",
        sa.Column("result_id", sa.String(length=128), primary_key=True),
        sa.Column("experiment_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("variant_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("conversion_count", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "outcome_events",
        sa.Column("outcome_id", sa.String(length=128), primary_key=True),
        sa.Column("trace_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("customer_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("experiment_id", sa.String(length=128), nullable=True),
        sa.Column("variant_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Drop initial platform tables."""
    op.drop_table("outcome_events")
    op.drop_table("experiment_results")
    op.drop_table("experiment_variants")
    op.drop_table("experiments")
    op.drop_table("approval_queue")
    op.drop_table("audit_log")
    op.drop_table("feature_store")
