"""Сила развития клана — показатель топа кланов.

Revision ID: b8f4d2a6c1e3
Revises: a7e3c9f1b4d6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8f4d2a6c1e3"
down_revision: Union[str, None] = "a7e3c9f1b4d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clans", sa.Column("dev_score", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_clans_dev_score", "clans", ["dev_score"])


def downgrade() -> None:
    op.drop_index("ix_clans_dev_score", table_name="clans")
    op.drop_column("clans", "dev_score")
