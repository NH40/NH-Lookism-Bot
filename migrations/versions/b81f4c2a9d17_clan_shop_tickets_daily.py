"""clan_shop_tickets_daily

Revision ID: b81f4c2a9d17
Revises: a7c3e91d2b40
Create Date: 2026-10-21 13:00:00

Дневной счётчик тикетов из клан-магазина (растущая цена + лимит 5 000 в сутки).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b81f4c2a9d17'
down_revision: Union[str, None] = 'a7c3e91d2b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clans', sa.Column('shop_tickets_day', sa.Date(), nullable=True))
    op.add_column('clans', sa.Column('shop_tickets_bought', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('clans', 'shop_tickets_bought')
    op.drop_column('clans', 'shop_tickets_day')
