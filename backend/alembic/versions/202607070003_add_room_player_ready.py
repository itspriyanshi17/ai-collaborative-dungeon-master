"""add room player ready

Revision ID: 202607070003
Revises: 202607070002
Create Date: 2026-07-08 00:00:03.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607070003"
down_revision: str | None = "202607070002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "room_players",
        sa.Column("is_ready", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.alter_column("room_players", "is_ready", server_default=None)


def downgrade() -> None:
    op.drop_column("room_players", "is_ready")
