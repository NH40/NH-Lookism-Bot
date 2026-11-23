"""Начинать онлайн-бои на автобое.

Revision ID: c4f2a8e1d6b9
Revises: b8f4d2a6c1e3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4f2a8e1d6b9"
down_revision: Union[str, None] = "b8f4d2a6c1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("arena_auto_default", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "arena_auto_default")
