"""Дань младших императоров: отметка и суточные счётчики. Отметка = уже собранное, чтобы
старшим не пришла дань за всё прошлое разом.

Revision ID: e7b3c5d9a1f2
Revises: d2f7a9c4e815
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7b3c5d9a1f2"
down_revision: Union[str, None] = "d2f7a9c4e815"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("tribute_mark", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("tribute_day", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("tribute_own", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("tribute_got", sa.BigInteger(), nullable=False, server_default="0"))
    op.execute("UPDATE users SET tribute_mark = empire_collected WHERE empire_collected <> 0")


def downgrade() -> None:
    for name in ("tribute_got", "tribute_own", "tribute_day", "tribute_mark"):
        op.drop_column("users", name)
