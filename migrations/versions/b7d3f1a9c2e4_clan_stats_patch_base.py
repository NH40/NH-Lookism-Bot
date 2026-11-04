"""clan_member_stats.patch_base — снимок вклада на момент патча ("этот патч" / "за всё время")

Revision ID: b7d3f1a9c2e4
Revises: a4c8e2f6b913
Create Date: 2026-11-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "b7d3f1a9c2e4"
down_revision: Union[str, None] = "a4c8e2f6b913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clan_member_stats", sa.Column("patch_base", JSONB, nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("clan_member_stats", "patch_base")
