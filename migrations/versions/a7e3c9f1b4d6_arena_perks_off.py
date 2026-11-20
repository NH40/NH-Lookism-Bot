"""Отключённые перки онлайн-боя.

Revision ID: a7e3c9f1b4d6
Revises: f3c8a1d5e9b2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7e3c9f1b4d6"
down_revision: Union[str, None] = "f3c8a1d5e9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("arena_perks_off", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("users", "arena_perks_off")
