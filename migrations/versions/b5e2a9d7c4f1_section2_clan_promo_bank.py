"""Раздел 2: кулдаун клана после выхода, объявления клана, группы промокодов, прайс банка.

Только новые nullable-колонки — живые данные не меняются.

Revision ID: b5e2a9d7c4f1
Revises: a3d8f1c6e2b9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "b5e2a9d7c4f1"
down_revision: Union[str, None] = "a3d8f1c6e2b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("clan_left_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clans", sa.Column("announcement", sa.Text(), nullable=True))
    op.add_column("clans", sa.Column("announcement_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("promo_codes", sa.Column("group_name", sa.String(32), nullable=True))
    op.create_index("ix_promo_codes_group_name", "promo_codes", ["group_name"])
    op.add_column("banks", sa.Column("prices", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("banks", "prices")
    op.drop_index("ix_promo_codes_group_name", table_name="promo_codes")
    op.drop_column("promo_codes", "group_name")
    op.drop_column("clans", "announcement_at")
    op.drop_column("clans", "announcement")
    op.drop_column("users", "clan_left_at")
