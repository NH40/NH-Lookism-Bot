"""clan_member_stats

Revision ID: a7c3e91d2b40
Revises: 21f5bf0520e5
Create Date: 2026-10-21 12:00:00

Статистика вклада участников клана (казна, рота, магазин, стройка, войны, обменник).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e91d2b40'
down_revision: Union[str, None] = '21f5bf0520e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _counter(name: str, big: bool = True) -> sa.Column:
    return sa.Column(name, sa.BigInteger() if big else sa.Integer(), server_default='0', nullable=False)


def upgrade() -> None:
    op.create_table(
        'clan_member_stats',
        sa.Column('clan_id', sa.Integer(), sa.ForeignKey('clans.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        _counter('treasury'),
        _counter('garrison_units'),
        _counter('garrison_power'),
        _counter('garrison_taken'),
        _counter('shop_spent'),
        _counter('build_spent'),
        _counter('wars', big=False),
        _counter('wars_won', big=False),
        _counter('lands_won', big=False),
        _counter('exchanges', big=False),
    )


def downgrade() -> None:
    op.drop_table('clan_member_stats')
