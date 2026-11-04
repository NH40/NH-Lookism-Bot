"""Переработка родословных, техник и путей: шкалы, выбор техник, Ультра инстинкт, ранги Самдака.

Только добавляет колонки, данные игроков не меняет. Единственное заполнение — разовая бесплатная
смена родословной всем, у кого она уже выбрана (решение пользователя 2026-11-04).

Revision ID: c9e1d4f7a2b6
Revises: b7d3f1a9c2e4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9e1d4f7a2b6"
down_revision: Union[str, None] = "b7d3f1a9c2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_paths", sa.Column("gauge", sa.Float(), nullable=False, server_default="0"))
    op.add_column("user_techniques", sa.Column("selected", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("statist_contracts", sa.Column("retain", sa.Float(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("free_bloodline_change", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("ultra_settings", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.add_column("users", sa.Column("rank_locks", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("users", sa.Column("security_off_until", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET free_bloodline_change = true WHERE bloodline IS NOT NULL")


def downgrade() -> None:
    op.drop_column("users", "security_off_until")
    op.drop_column("users", "rank_locks")
    op.drop_column("users", "ultra_settings")
    op.drop_column("users", "free_bloodline_change")
    op.drop_column("statist_contracts", "retain")
    op.drop_column("user_techniques", "selected")
    op.drop_column("user_paths", "gauge")
