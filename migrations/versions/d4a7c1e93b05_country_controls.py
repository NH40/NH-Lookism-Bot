"""Управление странами в админке: вход и бои. Новые колонки, данные не меняются.

Revision ID: d4a7c1e93b05
Revises: c9e1d4f7a2b6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a7c1e93b05"
down_revision: Union[str, None] = "c9e1d4f7a2b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("countries", sa.Column("entry_closed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("countries", sa.Column("battles_closed", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("countries", "battles_closed")
    op.drop_column("countries", "entry_closed")
