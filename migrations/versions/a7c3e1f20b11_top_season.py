"""top_season: снимок мощи для топа и журнал выплат наград сезона

Revision ID: a7c3e1f20b11
Revises: f5c6307ed996
Create Date: 2026-10-11 12:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7c3e1f20b11'
down_revision: Union[str, None] = 'f5c6307ed996'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('army_power_cache', sa.BigInteger(), server_default='0', nullable=False))
    op.create_index(op.f('ix_users_army_power_cache'), 'users', ['army_power_cache'], unique=False)
    op.create_table(
        'season_top_payouts',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('season_top_payouts')
    op.drop_index(op.f('ix_users_army_power_cache'), table_name='users')
    op.drop_column('users', 'army_power_cache')
