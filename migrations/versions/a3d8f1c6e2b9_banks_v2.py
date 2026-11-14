"""Банки v2: виды кредита (фикс/почасовой), заявки и договор, пеня, участники банка, рабство.

Существующие банки: дневная ставка → почасовая той же доходности (rate / 24), фикс выключен. Существующие кредиты
остаются видом `daily` и считаются по-старому.

Revision ID: a3d8f1c6e2b9
Revises: f7b2c4e9a1d3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3d8f1c6e2b9"
down_revision: Union[str, None] = "f7b2c4e9a1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("banks", "rate", existing_type=sa.Float(), nullable=True)
    op.add_column("banks", sa.Column("fixed_rate", sa.Float(), nullable=True))
    op.add_column("banks", sa.Column("hourly_rate", sa.Float(), nullable=True))
    op.add_column("banks", sa.Column("penalty_rate", sa.Float(), nullable=False, server_default="0"))
    op.execute("UPDATE banks SET hourly_rate = rate / 24 WHERE rate IS NOT NULL")

    op.create_table(
        "bank_members",
        sa.Column("bank_id", sa.Integer(), sa.ForeignKey("banks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, unique=True),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column("bank_loans", sa.Column("kind", sa.String(8), nullable=False, server_default="daily"))
    op.add_column("bank_loans", sa.Column("penalty", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("bank_loans", sa.Column("penalty_total", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("bank_loans", sa.Column("penalty_rate", sa.Float(), nullable=False, server_default="0"))
    op.add_column("bank_loans", sa.Column("terms", sa.Text(), nullable=True))
    op.add_column("bank_loans", sa.Column("approved_by", sa.BigInteger(), nullable=True))
    op.add_column("bank_loans", sa.Column("offer_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bank_loans", sa.Column("accrued_hours", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bank_loans", sa.Column("penalty_hours", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bank_loans", sa.Column("slave_pool", sa.BigInteger(), nullable=False, server_default="0"))


def downgrade() -> None:
    for col in ("slave_pool", "penalty_hours", "accrued_hours", "offer_until", "approved_by", "terms", "penalty_rate", "penalty_total",
                "penalty", "kind"):
        op.drop_column("bank_loans", col)
    op.drop_table("bank_members")
    for col in ("penalty_rate", "hourly_rate", "fixed_rate"):
        op.drop_column("banks", col)
