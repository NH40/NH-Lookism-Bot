"""Журнал статистов — триггер на оператор, а не на строку.

Хотфикс 2026-11-12: построчный `ledger_extras` на каждую изменённую стопку делал поиск и
UPDATE записи `player_ledger` (окно склейки 5 минут). У крупных игроков десятки тысяч
стопок — перевод лагеря одним запросом всё равно шёл ~2 минуты и держал соединение.
Теперь одна запись журнала на игрока за весь оператор: сумма изменений из переходных таблиц
(`REFERENCING ... TABLE`). Нулевой итог (перевод между лагерями) в журнал не пишется.

Revision ID: c8e2a5f9d1b3
Revises: f4a8d1b6c3e9
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c8e2a5f9d1b3"
down_revision: Union[str, None] = "f4a8d1b6c3e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FUNCS = (
    """
CREATE FUNCTION ledger_extras_ins() RETURNS trigger AS $$
BEGIN
    PERFORM ledger_write(s.user_id, 'statists', '', s.d, NULL, '')
    FROM (SELECT user_id, SUM(quantity)::bigint AS d FROM new_rows GROUP BY user_id) s
    WHERE s.d <> 0;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
""",
    """
CREATE FUNCTION ledger_extras_upd() RETURNS trigger AS $$
BEGIN
    PERFORM ledger_write(s.user_id, 'statists', '', s.d, NULL, '')
    FROM (
        SELECT n.user_id, SUM(n.quantity - o.quantity)::bigint AS d
        FROM new_rows n JOIN old_rows o ON o.id = n.id
        GROUP BY n.user_id
    ) s
    WHERE s.d <> 0;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
""",
    """
CREATE FUNCTION ledger_extras_del() RETURNS trigger AS $$
BEGIN
    PERFORM ledger_write(s.user_id, 'statists', '', s.d, NULL, '')
    FROM (SELECT user_id, -SUM(quantity)::bigint AS d FROM old_rows GROUP BY user_id) s
    WHERE s.d <> 0;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
""",
)


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ledger_extras ON extras")
    for sql in _FUNCS:
        op.execute(sql)
    op.execute(
        "CREATE TRIGGER ledger_extras_ins AFTER INSERT ON extras REFERENCING NEW TABLE AS new_rows "
        "FOR EACH STATEMENT EXECUTE FUNCTION ledger_extras_ins()"
    )
    op.execute(
        "CREATE TRIGGER ledger_extras_upd AFTER UPDATE ON extras REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows "
        "FOR EACH STATEMENT EXECUTE FUNCTION ledger_extras_upd()"
    )
    op.execute(
        "CREATE TRIGGER ledger_extras_del AFTER DELETE ON extras REFERENCING OLD TABLE AS old_rows "
        "FOR EACH STATEMENT EXECUTE FUNCTION ledger_extras_del()"
    )


def downgrade() -> None:
    for name in ("ins", "upd", "del"):
        op.execute(f"DROP TRIGGER IF EXISTS ledger_extras_{name} ON extras")
        op.execute(f"DROP FUNCTION IF EXISTS ledger_extras_{name}()")
    op.execute(
        "CREATE TRIGGER ledger_extras AFTER INSERT OR DELETE OR UPDATE OF quantity ON extras "
        "FOR EACH ROW EXECUTE FUNCTION ledger_extras()"
    )
