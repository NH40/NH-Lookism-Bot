"""mastery_quests

Цепочка «Преодоление стены»: одна строка на игрока, текущий этап (см.
`db/models/mastery_quest.py`). Написана вручную — Docker Desktop в момент разработки был
выключен (autogenerate недоступен); после применения проверить `alembic check`.

Revision ID: a7d1e2f3b4c5
Revises: 3c4e4115e89f
Create Date: 2026-10-01 12:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7d1e2f3b4c5'
down_revision: Union[str, None] = '3c4e4115e89f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mastery_quests',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('stage', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('tom_power', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('progress_trainings', sa.Integer(), server_default='0', nullable=False),
        sa.Column('progress_pvp_wins', sa.Integer(), server_default='0', nullable=False),
        sa.Column('equal_win', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('points_bought', sa.Integer(), server_default='0', nullable=False),
        sa.Column('points_free', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
    )
    op.create_index(op.f('ix_mastery_quests_status'), 'mastery_quests', ['status'], unique=False)
    op.create_index(op.f('ix_mastery_quests_available_at'), 'mastery_quests', ['available_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_mastery_quests_available_at'), table_name='mastery_quests')
    op.drop_index(op.f('ix_mastery_quests_status'), table_name='mastery_quests')
    op.drop_table('mastery_quests')
