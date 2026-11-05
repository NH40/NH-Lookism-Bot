"""Объявления императора. Новая таблица, данные не меняются.

Revision ID: e7b2f4a91c06
Revises: d4a7c1e93b05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7b2f4a91c06"
down_revision: Union[str, None] = "d4a7c1e93b05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "emperor_announcements",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("emperor_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("emperor_name", sa.String(length=128), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("city_ids", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("recipients", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("muted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_emperor_announcements_emperor_id", "emperor_announcements", ["emperor_id"])
    op.create_index("ix_emperor_announcements_city_ids", "emperor_announcements", ["city_ids"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_table("emperor_announcements")
