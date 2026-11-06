"""Снимок мощи клана для топа. Новая колонка, данные заполнит фоновый пересчёт при старте бота.

Revision ID: f3c9a1d7e2b4
Revises: e7b2f4a91c06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3c9a1d7e2b4"
down_revision: Union[str, None] = "e7b2f4a91c06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clans", sa.Column("power_cache", sa.BigInteger(), nullable=False, server_default="0"))
    op.create_index("ix_clans_power_cache", "clans", ["power_cache"])


def downgrade() -> None:
    op.drop_index("ix_clans_power_cache", table_name="clans")
    op.drop_column("clans", "power_cache")
