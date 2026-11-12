"""Шкала техники (CQC): user_techniques.gauge.

Revision ID: b6d3f8a1c2e4
Revises: a9c2e6f1d4b7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b6d3f8a1c2e4"
down_revision: Union[str, None] = "a9c2e6f1d4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_techniques", sa.Column("gauge", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("user_techniques", "gauge")
