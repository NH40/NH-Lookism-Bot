"""Хансу «Фокус тренировки»: users.training_focus — отряды [лагерь, ранг, школа] в фокусе тренировки статистов.

Revision ID: c8f1a4d2e9b7
Revises: b3e7d1a9c4f2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8f1a4d2e9b7"
down_revision: Union[str, None] = "b3e7d1a9c4f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("training_focus", postgresql.JSONB(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("users", "training_focus")
