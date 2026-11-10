"""Мастерство: очки за Тома бесплатно — тем, кто победил Тома, но не докупил очки, выдать оставшиеся.

Revision ID: d2f7a9c4e815
Revises: c8e4b1f60a27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d2f7a9c4e815"
down_revision: Union[str, None] = "c8e4b1f60a27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE mastery_quests SET points_free = points_free + (4 - points_bought), points_bought = 4 "
        "WHERE status = 'trainer' AND points_bought < 4"
    )


def downgrade() -> None:
    # Выданные очки могли быть уже вложены — откатить нельзя, схема не менялась.
    pass
