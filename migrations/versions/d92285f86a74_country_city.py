"""country/city

Revision ID: d92285f86a74
Revises: 1ce13a27b2c5
Create Date: 2026-09-21 00:00:00.000000

Написана вручную (не `alembic revision --autogenerate`) — в этом окружении нет доступа
к запущенному Postgres (см. CLAUDE.md, "Не проверено реальным запуском"), поэтому
autogenerate не может подключиться и сравнить схему. Содержимое напрямую отражает
`db/models/country.py`/`db/models/city.py`/`db/models/user.py` — сверить перед
`alembic upgrade head` на боевой БД.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd92285f86a74'
down_revision: Union[str, None] = '1ce13a27b2c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'countries',
        sa.Column('code', sa.String(length=2), autoincrement=False, nullable=False),
        sa.Column('name', sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint('code'),
    )
    op.create_table(
        'cities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('country_code', sa.String(length=2), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('district_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['country_code'], ['countries.code']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('country_code', 'name', name='uq_cities_country_name'),
    )
    op.create_index(op.f('ix_cities_country_code'), 'cities', ['country_code'], unique=False)

    op.add_column('users', sa.Column('country_code', sa.String(length=2), nullable=True))
    op.add_column('users', sa.Column('city_id', sa.Integer(), nullable=True))
    op.add_column(
        'users',
        sa.Column('phase', sa.String(length=16), server_default='gang', nullable=False),
    )
    op.create_foreign_key(
        op.f('fk_users_country_code_countries'), 'users', 'countries', ['country_code'], ['code']
    )
    op.create_foreign_key(op.f('fk_users_city_id_cities'), 'users', 'cities', ['city_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(op.f('fk_users_city_id_cities'), 'users', type_='foreignkey')
    op.drop_constraint(op.f('fk_users_country_code_countries'), 'users', type_='foreignkey')
    op.drop_column('users', 'phase')
    op.drop_column('users', 'city_id')
    op.drop_column('users', 'country_code')

    op.drop_index(op.f('ix_cities_country_code'), table_name='cities')
    op.drop_table('cities')
    op.drop_table('countries')
