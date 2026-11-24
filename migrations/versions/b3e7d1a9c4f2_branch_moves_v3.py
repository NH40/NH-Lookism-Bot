"""Приёмы ветвей v3: из наборов в бой убраны старые коды ступеней путей и родословных.

Было `path:<код>:<ступень 1–4>` / `blood:<код>:<ступень>`, стало `path:<код>:<приём 1–3>` (в наборе — без уровня).
Старые выключенные коды значили другое — их убираем, у игрока снова в бою сильнейшие (как без настройки).

Revision ID: b3e7d1a9c4f2
Revises: d7e3b9a2c5f1
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b3e7d1a9c4f2"
down_revision: Union[str, None] = "d7e3b9a2c5f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE users SET arena_perks_off = COALESCE((
            SELECT jsonb_agg(c) FROM jsonb_array_elements_text(arena_perks_off) AS c
            WHERE c NOT LIKE 'path:%' AND c NOT LIKE 'blood:%'
        ), '[]'::jsonb)
        WHERE EXISTS (SELECT 1 FROM jsonb_array_elements_text(arena_perks_off) AS c WHERE c LIKE 'path:%' OR c LIKE 'blood:%')
    """)


def downgrade() -> None:
    pass
