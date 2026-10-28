"""challenge_multi_outgoing

Revision ID: d4e8b2c61a93
Revises: c3d9a7e15f20
Create Date: 2026-10-28 15:00:00

Несколько исходящих вызовов одновременно: КД атаки — с момента вызова.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e8b2c61a93'
down_revision: Union[str, None] = 'c3d9a7e15f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('uq_challenge_pending_attacker', table_name='district_challenges')
    op.create_index('ix_challenge_attacker', 'district_challenges', ['attacker_id'])


def downgrade() -> None:
    op.drop_index('ix_challenge_attacker', table_name='district_challenges')
    op.create_index(
        'uq_challenge_pending_attacker', 'district_challenges', ['attacker_id'], unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
