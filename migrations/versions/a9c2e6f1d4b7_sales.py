"""«Пятницы»: события скидок, выбор «избранных», разовые покупки.

Revision ID: a9c2e6f1d4b7
Revises: f4a8d1b6c3e9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9c2e6f1d4b7"
down_revision: Union[str, None] = "f4a8d1b6c3e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sale_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("started_by", sa.BigInteger(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sale_events_ends_at", "sale_events", ["ends_at"])
    op.create_table(
        "sale_choices",
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("sale_events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("categories", postgresql.ARRAY(sa.String(16)), nullable=False, server_default="{}"),
    )
    op.create_table(
        "sale_purchases",
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("sale_events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sale_purchases")
    op.drop_table("sale_choices")
    op.drop_index("ix_sale_events_ends_at", table_name="sale_events")
    op.drop_table("sale_events")
