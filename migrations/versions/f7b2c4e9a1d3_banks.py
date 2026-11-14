"""Банки игроков и кредиты: banks, bank_loans.

Revision ID: f7b2c4e9a1d3
Revises: e2a7c9d4f6b1
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7b2c4e9a1d3"
down_revision: Union[str, None] = "e2a7c9d4f6b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "banks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("capital", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("min_days", sa.Integer(), nullable=False),
        sa.Column("max_days", sa.Integer(), nullable=False),
        sa.Column("lent_total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("earned_total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "bank_loans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bank_id", sa.Integer(), sa.ForeignKey("banks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("lender_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("borrower_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("principal", sa.BigInteger(), nullable=False),
        sa.Column("interest", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("paid", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accrued_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("frozen_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bank_loans_borrower_status", "bank_loans", ["borrower_id", "status"])
    op.create_index("ix_bank_loans_bank_status", "bank_loans", ["bank_id", "status"])
    op.create_index("ix_bank_loans_status_due", "bank_loans", ["status", "due_at"])


def downgrade() -> None:
    op.drop_table("bank_loans")
    op.drop_table("banks")
