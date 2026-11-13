"""Родословная Пеньгуана: временные бафы и павшие для выкупа.

Revision ID: d4f1b8e6a3c7
Revises: b6d3f8a1c2e4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4f1b8e6a3c7"
down_revision: Union[str, None] = "b6d3f8a1c2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "penguan_buffs",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("kind", sa.String(16), primary_key=True),
        sa.Column("until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("power", sa.Float(), nullable=False),
    )
    op.create_table(
        "penguan_fallen",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("camp", sa.String(16), nullable=False),
        sa.Column("rows", postgresql.JSONB(), nullable=False),
        sa.Column("until", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("penguan_fallen")
    op.drop_table("penguan_buffs")
