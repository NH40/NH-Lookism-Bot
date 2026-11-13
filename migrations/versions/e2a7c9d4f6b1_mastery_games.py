"""Мини-игры мастерства вместо Тома Ли: mastery_quests.games_done.

Revision ID: e2a7c9d4f6b1
Revises: d4f1b8e6a3c7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2a7c9d4f6b1"
down_revision: Union[str, None] = "d4f1b8e6a3c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mastery_quests", sa.Column("games_done", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("mastery_quests", "games_done")
