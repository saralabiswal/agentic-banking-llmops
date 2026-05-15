"""${message}."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | tuple[str, ...] | None = ${repr(branch_labels)}
depends_on: str | tuple[str, ...] | None = ${repr(depends_on)}


def upgrade() -> None:
    """Apply the migration."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Revert the migration."""
    ${downgrades if downgrades else "pass"}
