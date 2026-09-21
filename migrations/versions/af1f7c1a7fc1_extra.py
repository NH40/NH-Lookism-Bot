"""extra

Revision ID: af1f7c1a7fc1
Revises: 654759350969
Create Date: 2026-09-21 15:55:00.000000

Восстановлен вручную с ТЕМ ЖЕ revision id, что был у оригинала: первый прогон этой
автогенерации совпал с падением бота на несвязанном баге импорта в момент старта
контейнера (см. CLAUDE.md) — `alembic upgrade head` в entrypoint успел применить DDL
(`extras` уже реально в БД) ДО того, как процесс бота упал, а сам файл миграции затем
был удалён вместе с ошибочной генерацией. Восстановление тем же revision id — синхронизация
файла с уже применённым состоянием БД, не новая миграция.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af1f7c1a7fc1'
down_revision: Union[str, None] = '654759350969'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'extras',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('rank', sa.String(length=8), nullable=False),
        sa.Column('power', sa.Integer(), nullable=False),
        sa.Column('camp', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_extras_user_id'), 'extras', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_extras_user_id'), table_name='extras')
    op.drop_table('extras')
