"""influence_banked

Revision ID: c3d9a7e15f20
Revises: b81f4c2a9d17
Create Date: 2026-10-28 12:00:00

Копилка влияния императора. Бэкфилл для уже коронованных: районы их городов на момент
коронации были их (+1 влияния за район) — восстанавливаем по городам, которые они держат.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d9a7e15f20'
down_revision: Union[str, None] = 'b81f4c2a9d17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('influence_banked', sa.Integer(), server_default='0', nullable=False))
    op.execute(
        "UPDATE users u SET influence_banked = s.d FROM ("
        "  SELECT emperor_id, SUM(district_count) AS d FROM cities WHERE emperor_id IS NOT NULL GROUP BY emperor_id"
        ") s WHERE u.id = s.emperor_id AND u.phase = 'fist'"
    )


def downgrade() -> None:
    op.drop_column('users', 'influence_banked')
