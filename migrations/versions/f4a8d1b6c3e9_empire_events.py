"""Ивенты императора: таблицы ивентов и получений.

Revision ID: f4a8d1b6c3e9
Revises: e7b3c5d9a1f2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4a8d1b6c3e9"
down_revision: Union[str, None] = "e7b3c5d9a1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "empire_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("emperor_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("pool", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("slots", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("spent", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("claims", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_empire_events_active_kind", "empire_events", ["emperor_id", "kind"], unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_empire_events_status_ends", "empire_events", ["status", "ends_at"])
    op.create_table(
        "empire_event_claims",
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("empire_events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("empire_event_claims")
    op.drop_index("ix_empire_events_status_ends", table_name="empire_events")
    op.drop_index("uq_empire_events_active_kind", table_name="empire_events")
    op.drop_table("empire_events")
