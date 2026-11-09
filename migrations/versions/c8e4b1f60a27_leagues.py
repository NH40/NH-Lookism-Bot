"""Лиги: длиннее код страны, лига и счёт у игрока. Существующие данные не меняются.

Revision ID: c8e4b1f60a27
Revises: a1d5e8c2f7b3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8e4b1f60a27"
down_revision: Union[str, None] = "a1d5e8c2f7b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (("countries", "code"), ("cities", "country_code"), ("users", "country_code"))


def _resize(old: int, new: int) -> None:
    """Триггер журнала зависит от `users.country_code`: снять на время смены типа и вернуть как был."""
    ddl = op.get_bind().execute(sa.text("SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE tgname = 'ledger_users_profile'")).scalar_one()
    op.execute("DROP TRIGGER ledger_users_profile ON users")
    for table, column in _COLUMNS:
        op.alter_column(table, column, type_=sa.String(length=new), existing_type=sa.String(length=old))
    op.execute(ddl)


def upgrade() -> None:
    _resize(2, 4)
    op.add_column("users", sa.Column("league", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("league_score", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_users_league", "users", ["league"])


def downgrade() -> None:
    op.drop_index("ix_users_league", table_name="users")
    op.drop_column("users", "league_score")
    op.drop_column("users", "league")
    _resize(4, 2)
