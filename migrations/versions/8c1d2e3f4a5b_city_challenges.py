"""city_challenges

Вызов круга за все районы игрока в городе: `district_challenges.scope`/`city_id`,
`district_id` становится необязательным, частичный уникальный индекс на один висящий
вызов за город на одного защитника.

Revision ID: 8c1d2e3f4a5b
Revises: 05b68e9f372f
Create Date: 2026-09-30 12:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c1d2e3f4a5b'
down_revision: Union[str, None] = '05b68e9f372f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'district_challenges',
        sa.Column('scope', sa.String(length=16), server_default='district', nullable=False),
    )
    op.add_column('district_challenges', sa.Column('city_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'district_challenges_city_id_fkey', 'district_challenges', 'cities', ['city_id'], ['id']
    )
    op.create_index(op.f('ix_district_challenges_city_id'), 'district_challenges', ['city_id'], unique=False)
    op.alter_column('district_challenges', 'district_id', existing_type=sa.Integer(), nullable=True)
    # Существующие вызовы (все — за район) получают город своего района.
    op.execute(
        "UPDATE district_challenges dc SET city_id = d.city_id FROM districts d WHERE d.id = dc.district_id"
    )
    op.create_index(
        'uq_challenge_pending_city_defender',
        'district_challenges',
        ['city_id', 'defender_id'],
        unique=True,
        postgresql_where=sa.text("status = 'pending' AND scope = 'city'"),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_challenge_pending_city_defender',
        table_name='district_challenges',
        postgresql_where=sa.text("status = 'pending' AND scope = 'city'"),
    )
    op.execute("DELETE FROM district_challenges WHERE scope = 'city'")
    op.alter_column('district_challenges', 'district_id', existing_type=sa.Integer(), nullable=False)
    op.drop_index(op.f('ix_district_challenges_city_id'), table_name='district_challenges')
    op.drop_constraint('district_challenges_city_id_fkey', 'district_challenges', type_='foreignkey')
    op.drop_column('district_challenges', 'city_id')
    op.drop_column('district_challenges', 'scope')
