"""mastery_breakthrough

Revision ID: e5f1c8a2d406
Revises: d4e8b2c61a93
Create Date: 2026-10-28 18:00:00

Мастерство: тренировки статистов в заданиях; этапы 2–3, ещё не начатые (pending), ждут прорыва.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f1c8a2d406'
down_revision: Union[str, None] = 'd4e8b2c61a93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('mastery_quests', sa.Column('progress_extras', sa.Integer(), server_default='0', nullable=False))
    # «Не трогаем достигнутое»: пройденные этапы и очки остаются; ещё не начатый следующий этап
    # (pending, этап 2+) теперь сначала требует прорыва. Активные задания — без изменений.
    op.execute("UPDATE mastery_quests SET status = 'breakthrough' WHERE status = 'pending' AND stage >= 2")
    # Активные задания — без новых требований: новые тренировочные пункты (STAGE_TASKS 2026-10-28)
    # засчитываем сразу; этап 2 раньше просил 10 личных, теперь 12 — +2 к прогрессу.
    op.execute("UPDATE mastery_quests SET progress_extras = 4, progress_trainings = 6 WHERE status = 'active' AND stage = 1")
    op.execute("UPDATE mastery_quests SET progress_extras = 8, progress_trainings = progress_trainings + 2 WHERE status = 'active' AND stage = 2")
    op.execute("UPDATE mastery_quests SET progress_extras = 10, progress_trainings = 15 WHERE status = 'active' AND stage = 3")


def downgrade() -> None:
    op.execute("UPDATE mastery_quests SET status = 'pending', available_at = now() WHERE status = 'breakthrough'")
    op.drop_column('mastery_quests', 'progress_extras')
