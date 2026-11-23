"""Заявки на районы после перехода в другую лигу.

Revision ID: d7e3b9a2c5f1
Revises: c4f2a8e1d6b9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7e3b9a2c5f1"
down_revision: Union[str, None] = "c4f2a8e1d6b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "league_claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("district_id", sa.Integer(), sa.ForeignKey("districts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("buildings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(8), nullable=False, server_default="open"),
        sa.Column("challenge_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_league_claims_user_id", "league_claims", ["user_id"])
    op.create_index("ix_league_claims_status", "league_claims", ["status"])
    op.create_index("ix_league_claims_challenge_id", "league_claims", ["challenge_id"])


def downgrade() -> None:
    op.drop_table("league_claims")
