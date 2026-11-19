"""Слоты пути Копирования и техники мастерства (раздел 4).

Слоты заполняются из текущей памяти боёв — у игроков с копирующим путём копии не пропадут при выкладке.

Revision ID: d4a7e2c9b1f6
Revises: c8f3b1e6a2d4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a7e2c9b1f6"
down_revision: Union[str, None] = "c8f3b1e6a2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "path_copy_slots",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("slot", sa.Integer(), primary_key=True),
        sa.Column("path_code", sa.String(32), nullable=False),
        sa.Column("path_level", sa.Integer(), nullable=False),
        sa.Column("opponent_id", sa.BigInteger(), nullable=True),
        sa.Column("copied_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "mastery_techniques",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("mastery", sa.String(16), primary_key=True),
        sa.Column("tier", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("learned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Слоты: 1 + по одному на 4, 7, 10 уровне копирующего пути; берём свежие воспоминания без копирующих путей.
    op.execute("""
        INSERT INTO path_copy_slots (user_id, slot, path_code, path_level, opponent_id)
        SELECT user_id, rn, path_code, path_level, opponent_id FROM (
            SELECT m.user_id, m.path_code, m.path_level, m.opponent_id,
                   row_number() OVER (PARTITION BY m.user_id ORDER BY m.fought_at DESC, m.id DESC) AS rn,
                   1 + (p.level >= 4)::int + (p.level >= 7)::int + (p.level >= 10)::int AS slots
            FROM battle_memory m
            JOIN users u ON u.id = m.user_id
            JOIN user_paths p ON p.user_id = u.id AND p.code = u.active_path
            WHERE u.active_path IN ('copy', 'infinite') AND m.path_code NOT IN ('copy', 'infinite')
        ) x WHERE rn <= slots
    """)


def downgrade() -> None:
    op.drop_table("mastery_techniques")
    op.drop_table("path_copy_slots")
