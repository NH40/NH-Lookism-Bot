"""potential_points

Revision ID: f6a2d9b3e517
Revises: e5f1c8a2d406
Create Date: 2026-10-28 20:00:00

Очки потенциала: копятся за активность, повышают потенциал на ступень.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f6a2d9b3e517'
down_revision: Union[str, None] = 'e5f1c8a2d406'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('potential_points', sa.BigInteger(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('potential_point_gates', postgresql.JSONB(), server_default='{}', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'potential_point_gates')
    op.drop_column('users', 'potential_points')
