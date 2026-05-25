"""Durable evaluation history tables.

Author: Sarala Biswal
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "002_evaluation_history"
down_revision: str | None = "001_initial_schema"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Create durable offline evaluation and LLM judge history tables."""
    op.create_table(
        "evaluation_reports",
        sa.Column("report_id", sa.String(length=128), primary_key=True),
        sa.Column("trace_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("model_name", sa.String(length=128), nullable=False, index=True),
        sa.Column("candidate_version", sa.String(length=64), nullable=False),
        sa.Column("champion_version", sa.String(length=64), nullable=True),
        sa.Column("gates", sa.JSON(), nullable=False),
        sa.Column("overall_passed", sa.Boolean(), nullable=False),
        sa.Column("promotion_allowed", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "evaluation_judge_results",
        sa.Column("judge_id", sa.String(length=128), primary_key=True),
        sa.Column("trace_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade() -> None:
    """Drop durable evaluation history tables."""
    op.drop_table("evaluation_judge_results")
    op.drop_table("evaluation_reports")
