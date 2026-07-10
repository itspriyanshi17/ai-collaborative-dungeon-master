"""create room tables

Revision ID: 202607070002
Revises: 202607070001
Create Date: 2026-07-07 00:00:02.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607070002"
down_revision: str | None = "202607070001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("host_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["host_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rooms_code"), "rooms", ["code"], unique=True)
    op.create_index(op.f("ix_rooms_host_user_id"), "rooms", ["host_user_id"], unique=False)

    op.create_table(
        "room_players",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_connected", sa.Boolean(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id", "user_id", name="uq_room_players_room_user"),
    )
    op.create_index(op.f("ix_room_players_room_id"), "room_players", ["room_id"], unique=False)
    op.create_index(op.f("ix_room_players_user_id"), "room_players", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_room_players_user_id"), table_name="room_players")
    op.drop_index(op.f("ix_room_players_room_id"), table_name="room_players")
    op.drop_table("room_players")
    op.drop_index(op.f("ix_rooms_host_user_id"), table_name="rooms")
    op.drop_index(op.f("ix_rooms_code"), table_name="rooms")
    op.drop_table("rooms")
