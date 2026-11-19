"""Рейды на игроков.

Revision ID: e1b9c4d7f2a3
Revises: d4a7e2c9b1f6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "e1b9c4d7f2a3"
down_revision: Union[str, None] = "d4a7e2c9b1f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raids",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("difficulty", sa.String(8), nullable=False),
        sa.Column("power", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", JSONB(), nullable=True),
    )
    op.create_index("ix_raids_user_id", "raids", ["user_id"])
    op.create_index("ix_raids_status", "raids", ["status"])
    op.create_index("ix_raids_starts_at", "raids", ["starts_at"])


def downgrade() -> None:
    op.drop_table("raids")
