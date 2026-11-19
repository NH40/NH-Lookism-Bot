"""Лига-обучение: строка на игрока. Все, кто уже есть, — `legacy` (обучение для них добровольное).

Revision ID: c8f3b1e6a2d4
Revises: b5e2a9d7c4f1
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c8f3b1e6a2d4"
down_revision: Union[str, None] = "b5e2a9d7c4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tutorial_runs",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("voluntary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("map", JSONB(), nullable=True),
        sa.Column("base", JSONB(), nullable=True),
        sa.Column("accrued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("INSERT INTO tutorial_runs (user_id, status) SELECT id, 'legacy' FROM users")


def downgrade() -> None:
    op.drop_table("tutorial_runs")
