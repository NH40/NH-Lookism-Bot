"""sbp_payments — счета на оплату по СБП (API ЮKassa)

Revision ID: a4c8e2f6b913
Revises: f6a2d9b3e517
Create Date: 2026-10-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4c8e2f6b913"
down_revision: Union[str, None] = "f6a2d9b3e517"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sbp_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("yookassa_id", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount_rub", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("confirmation_url", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sbp_payments_user_id", "sbp_payments", ["user_id"])
    op.create_index("ix_sbp_payments_status_created", "sbp_payments", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("sbp_payments")
