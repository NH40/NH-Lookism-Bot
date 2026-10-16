"""Админка — журналы (тексты)."""
from __future__ import annotations

import json

from bot.utils.formatting import esc, format_number as n

SEP = "━━━━━━━━━━━━━━━━━━"
BTN_AUDIT = "🛡 Действия админов"
BTN_PAY = "💳 Платежи"
BTN_BM = "🕶 Чёрный рынок"
BTN_CLAN = "🏰 Клан-донат"
BTN_FILTER = "👤 Фильтр по админу"
BTN_ALL = "♾ Все админы"
BTN_BACK = "◀️ К журналам"
BTN_TAB_AUDIT = "🛡 Админ"
BTN_TAB_PAY = "💳 Платежи"
BTN_TAB_ACT = "🎮 Активность"
MENU = f"📜 <b>Журналы</b>\n{SEP}\n<i>Выбери журнал:</i>"
EMPTY = "<i>Записей нет.</i>"
FILTER_TITLE = f"👤 <b>Фильтр по админу</b>\n{SEP}\n<i>Чьи действия показать:</i>"
EXCHANGE_NOTE = "<i>История сделок биржи не хранится — раздела нет.</i>"


def _ts(dt) -> str:
    return dt.strftime("%d.%m %H:%M") if dt else "—"


def _who(uid: int, username: str | None) -> str:
    return f"@{esc(username)}" if username else f"<code>{uid}</code>"


def _details(d: dict | None) -> str:
    if not d:
        return ""
    s = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    return esc(s if len(s) <= 60 else s[:57] + "…")


def audit_page(rows, total: int, page: int, per: int, title_suffix: str = "") -> str:
    pages = max(1, -(-total // per))
    lines = [
        f"{_ts(r.created_at)} · <code>{r.admin_id}</code> · <b>{esc(r.action)}</b>"
        + (f" → <code>{r.target_id}</code>" if r.target_id else "")
        + (f"\n   <i>{_details(r.details)}</i>" if r.details else "")
        for r in rows
    ]
    body = "\n".join(lines) or EMPTY
    return f"🛡 <b>Действия админов</b>{title_suffix}\n{SEP}\n{body}\n{SEP}\n<i>Стр. {page + 1}/{pages} · всего {n(total)}</i>"


def payments_page(rows, total: int, page: int, per: int, *, title: str = "💳 <b>Платежи</b>") -> str:
    pages = max(1, -(-total // per))
    lines = [f"{_ts(ts)} · {_who(uid, un)} · <b>{n(rub)} ₽</b> → {n(coins)} 💎" for uid, un, rub, coins, ts in rows]
    return f"{title}\n{SEP}\n{chr(10).join(lines) or EMPTY}\n{SEP}\n<i>Стр. {page + 1}/{pages} · всего {n(total)}</i>"


def blackmarket(rows) -> str:
    lines = [f"{esc(kind)} · <code>{esc(code)}</code> — <b>{n(cnt)}</b> покуп., макс. ур. {lvl}" for kind, code, cnt, lvl in rows]
    return (
        f"🕶 <b>Чёрный рынок</b>\n{SEP}\n{chr(10).join(lines) or EMPTY}\n{SEP}\n"
        "<i>В таблице нет дат — показана сводка по товарам.</i>"
    )


def clan_page(rows, total: int, page: int, per: int) -> str:
    pages = max(1, -(-total // per))
    lines = [f"{_ts(ts)} · 🏰 {esc(clan)} · {_who(uid, un)} · <b>{n(price)}</b>" for clan, uid, un, price, ts in rows]
    return f"🏰 <b>Клан-донат</b>\n{SEP}\n{chr(10).join(lines) or EMPTY}\n{SEP}\n<i>Стр. {page + 1}/{pages} · всего {n(total)}</i>"


def activity_page(rows, total: int, page: int, per: int) -> str:
    pages = max(1, -(-total // per))
    lines = [f"{_ts(ts)} · {esc(kind)}: {esc(txt)}" for kind, txt, ts in rows]
    return f"🎮 <b>Активность игрока</b>\n{SEP}\n{chr(10).join(lines) or EMPTY}\n{SEP}\n<i>Стр. {page + 1}/{pages} · всего {n(total)}</i>"


def player_header(uid: int) -> str:
    return f" · <code>{uid}</code>"
