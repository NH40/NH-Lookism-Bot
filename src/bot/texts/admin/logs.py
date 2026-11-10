"""Админка — журналы (тексты)."""
from __future__ import annotations

import json

from bot.config.card import CARD_BY_CODE
from bot.constant.ledger import (
    ASSET_CARD,
    ASSET_PROFILE,
    BATTLE_BOSS,
    BATTLE_BOTS,
    BATTLE_CITY,
    BATTLE_PVP,
    BATTLE_THRONE,
    BATTLE_TOM,
    BATTLE_WAR,
    REASON_ELITE_LOOT,
    REASON_EMPEROR_TAX,
    REASON_EMPEROR_TRIBUTE,
    REASON_INCOME,
    REASON_MANAGER_BURN,
    REASON_SABOTAGE,
    REASON_WAR_TREASURY,
)
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
BTN_TAB_COINS = "🪙 Монеты"
BTN_TAB_GOODS = "🎒 Имущество"
BTN_TAB_CHANGES = "👤 Изменения"
BTN_TAB_BATTLES = "⚔️ Бои"
BTN_ERRORS = "🛠 Ошибки"
BTN_SLOW = "🐢 Медленное"
BTN_BIG = "💸 Крупные суммы"
BTN_UPSETS = "⚖️ Перекосы боёв"
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


_REASONS = {
    REASON_INCOME: "Доход зданий",
    REASON_EMPEROR_TAX: "Налог императору",
    REASON_EMPEROR_TRIBUTE: "Дань младших императоров",
    REASON_MANAGER_BURN: "Менеджер: сожжено при атаке",
    REASON_ELITE_LOOT: "Элита: добыча в бою",
    REASON_SABOTAGE: "Саботаж: кража из казны",
    REASON_WAR_TREASURY: "Казна в войне или бою за трон",
}
_SOURCES = {
    "adm": "Админка", "admin": "Админка", "biz": "Бизнес", "business": "Бизнес", "clan": "Клан", "ex": "Биржа", "exchange": "Биржа",
    "recruit": "Вербовка", "training": "Тренировка", "school": "Школа", "shop": "Магазин", "potion": "Зелья", "contract": "Контракты",
    "casino": "Казино", "poker": "Покер", "deposit": "Вклады", "storage": "Ячейки", "genius": "Гениальность", "bm": "Чёрный рынок",
    "mastery": "Мастерство", "gang": "Банда", "path": "Путь", "bloodline": "Родословная", "awaken": "Пробуждение", "dn": "Донат", "donate": "Донат",
    "district": "Бой за район", "empire": "Империя", "war": "Война", "map": "Карта", "event": "Событие", "gacha": "Крутка", "bp": "Пасс", "q": "Задания",
    "travel": "Переезд", "profile": "Профиль", "tech": "Техника", "players": "Игроки", "stats": "Характеристики",
}
_ASSETS = {
    "nh": "🪙", "donate": "💎", "tickets": "🎟 тикетов", "statists": "👥 статистов", "card": "🃏", "district": "🏘 районов", "building": "🏢",
    "dev_points": "очков развития", "potential_points": "очков потенциала", "path_points": "очков пути", "path_fragments": "фрагментов пути",
    "technique_fragments": "фрагментов техник", "genius_fragments": "фрагментов гениев", "blood_drops": "🩸 капель крови", "skip_scrolls": "свитков пропуска",
}
_FIELDS = {
    "phase": "Фаза", "country_code": "Страна", "city_id": "Город", "potential": "Потенциал", "monster_potential": "67 MONSTER", "bloodline": "Родословная",
    "bloodline_level": "Уровень родословной", "bloodline2": "Родословная 2", "bloodline2_level": "Уровень родословной 2", "active_path": "Путь", "active_path2": "Путь 2",
    "active_technique": "Техника", "active_genius": "Гениальность", "path_stage": "Стадия пути", "awakening_level": "Пробуждение", "second_body": "Второе тело",
    "is_banned": "Бан", "admin_role": "Роль", "stat_strength": "Сила", "stat_speed": "Скорость", "stat_endurance": "Выносливость", "stat_agility": "Ловкость",
    "mastery_strength": "Мастерство силы", "mastery_speed": "Мастерство скорости", "mastery_endurance": "Мастерство выносливости", "mastery_technique": "Мастерство техники",
    "business_level": "Уровень бизнеса", "business_capacity": "Вместимость бизнеса",
}
_BATTLES = {
    BATTLE_BOTS: "Боты", BATTLE_CITY: "Город", BATTLE_PVP: "PvP", BATTLE_BOSS: "Босс", BATTLE_TOM: "Том Ли", BATTLE_THRONE: "Трон", BATTLE_WAR: "Война",
}
TITLE_COINS = "🪙 <b>Монеты игрока</b>"
TITLE_GOODS = "🎒 <b>Имущество игрока</b>"
TITLE_CHANGES = "👤 <b>Изменения игрока</b>"
TITLE_BATTLES = "⚔️ <b>Бои игрока</b>"
TITLE_UPSETS = "⚖️ <b>Перекосы боёв</b> — победа над вдвое более сильным"
_MAX_TEXT = 3900


def _footer(total: int, page: int, per: int) -> str:
    pages = max(1, -(-total // per))
    return f"<i>Стр. {page + 1}/{pages} · всего {n(total)}</i>"


def ledger_origin(reason: str, source: str) -> str:
    """Откуда запись: явная причина или раздел игры, и сам источник."""
    if reason in _REASONS:
        return f"{_REASONS[reason]} · {source}"
    if source.startswith("cb:"):
        section = source[3:].split(":")[0]
    elif source.startswith("api:"):
        parts = source.split("/")
        section = parts[2] if len(parts) > 2 else ""
    else:
        section = ""
    title = _SOURCES.get(section)
    return f"{title} · {source}" if title else source


def ledger_title(asset: str, item: str, delta: int, balance: int | None, note: str) -> str:
    if asset == ASSET_PROFILE:
        return f"{_FIELDS.get(item, item)}: {note}"
    name = _ASSETS.get(asset, asset)
    if asset == ASSET_CARD:
        card = CARD_BY_CODE.get(item)
        name = f"{name} {card.name if card else item}"
    elif item:
        name = f"{name} {item}"
    tail = f" → {n(balance)}" if balance is not None else ""
    return f"{'+' if delta > 0 else ''}{n(delta)} {name}{tail}"


def ledger_page(title: str, rows, total: int, page: int, per: int) -> str:
    lines = []
    for asset, item, delta, balance, note, reason, source, hits, ts in rows:
        times = f" ×{hits}" if hits > 1 else ""
        lines.append(f"{_ts(ts)} · <b>{esc(ledger_title(asset, item, delta, balance, note))}</b>\n   {esc(ledger_origin(reason, source))}{times}")
    return f"{title}\n{SEP}\n{chr(10).join(lines) or EMPTY}\n{SEP}\n{_footer(total, page, per)}"


def ledger_item(r) -> dict:
    asset, item, delta, balance, note, reason, source, hits, ts = r
    return {"title": ledger_title(asset, item, delta, balance, note), "sub": ledger_origin(reason, source) + (f" ×{hits}" if hits > 1 else ""), "created_at": ts}


def _big_parts(r) -> tuple[str, str]:
    user_id, name, asset, item, delta, balance, note, reason, source, hits, _ts_ = r
    return f"{name}: {ledger_title(asset, item, delta, balance, note)}", f"id {user_id} · {ledger_origin(reason, source)}" + (f" ×{hits}" if hits > 1 else "")


def big_moves_page(rows, total: int, page: int, per: int) -> str:
    lines = []
    for r in rows:
        head, sub = _big_parts(r)
        lines.append(f"{_ts(r[-1])} · <b>{esc(head)}</b>\n   {esc(sub)}")
    return f"💸 <b>Крупные суммы за сутки</b>\n{SEP}\n{chr(10).join(lines) or EMPTY}\n{SEP}\n{_footer(total, page, per)}"


def big_item(r) -> dict:
    head, sub = _big_parts(r)
    return {"title": head, "sub": sub, "created_at": r[-1]}


def _battle_head(r) -> str:
    defender = r.d_name if r.defender_id else "боты"
    return f"{_BATTLES.get(r.kind, r.kind)}: {r.a_name} {'🏆' if r.attacker_won else '💀'} — {defender}"


def _battle_sub(r) -> str:
    return (
        f"напал {n(r.a_quantity)} (мощь {n(r.a_power)}), погибло {n(r.a_dead)} · "
        f"защита {n(r.d_quantity)} (мощь {n(r.d_power)}), погибло {n(r.d_dead)} · раундов {r.rounds}"
    )


def battles_page(title: str, rows, total: int, page: int, per: int) -> str:
    lines = []
    for r in rows:
        mark = f"#{r.id} · " if r.details else ""
        notes = f"\n   {esc(r.notes.replace(chr(10), ' · '))}" if r.notes else ""
        lines.append(f"{mark}{_ts(r.created_at)} · <b>{esc(_battle_head(r))}</b>\n   {esc(_battle_sub(r))}{notes}")
    return f"{title}\n{SEP}\n{chr(10).join(lines) or EMPTY}\n{SEP}\n{_footer(total, page, per)}"


def _side_lines(title: str, side: dict) -> list[str]:
    lines = [
        title,
        f"увор {side['dodge']:.0%}, блок {side['block']:.0%}, контра {side['counter']:.0%}, побег {side['flee']:.0%}, поглощение {side['absorb']:.0%}, "
        f"сохранение {side['loss_save']:.0%}, влияние {side['influence']}",
    ]
    if side["mods"]:
        lines.append("итог: " + ", ".join(f"{k} {v}" for k, v in side["mods"].items()))
    for source, mods in side["sources"].items():
        if mods:
            lines.append(f"{source}: " + ", ".join(f"{k} {v}" for k, v in mods.items()))
    if side["triggers"]:
        lines.append("навыки: " + ", ".join(side["triggers"]))
    return lines


def battle_lines(r) -> list[str]:
    """Подробности боя простым текстом: для бота и Mini App."""
    if not r.details:
        return []
    lines = []
    for x in r.details["rounds"]:
        fired = "; ".join(filter(None, (", ".join(x["a_fired"]), ", ".join(x["d_fired"]))))
        chaos = " хаос" if x["a_chaos"] or x["d_chaos"] else ""
        lines.append(f"Р{x['n']}: напавший {n(x['a_dmg'])} урона, убил {n(x['a_kills'])}; защита {n(x['d_dmg'])}, убила {n(x['d_kills'])}{chaos}" + (f" [{fired}]" if fired else ""))
    return lines + [""] + _side_lines(f"Напавший ({r.a_name})", r.details["attacker"]) + [""] + _side_lines(f"Защита ({r.d_name})", r.details["defender"])


def battle_view(r) -> str:
    if r is None:
        return EMPTY
    head = f"⚔️ <b>{esc(_battle_head(r))}</b>\n{esc(_battle_sub(r))}\n"
    body = esc("\n".join(([r.notes, ""] if r.notes else []) + battle_lines(r)))
    return f"{head}{SEP}\n{body}"[:_MAX_TEXT]


def battle_item(r) -> dict:
    return {"title": _battle_head(r), "sub": _battle_sub(r), "lines": ([r.notes, ""] if r.notes else []) + battle_lines(r), "created_at": r.created_at}


def errors_page(rows, total: int, page: int, per: int) -> str:
    lines = [f"#{r.id} · {_ts(r.last_seen)} · {esc(r.process)} ×{n(r.hits)}\n   <b>{esc(r.title[:150])}</b>\n   {esc(r.source)}" for r in rows]
    return f"🛠 <b>Ошибки</b>\n{SEP}\n{chr(10).join(lines) or EMPTY}\n{SEP}\n{_footer(total, page, per)}"


def slow_page(rows, total: int, page: int, per: int) -> str:
    lines = [f"{_ts(r.last_seen)} · {esc(r.process)} ×{n(r.hits)}, до {n(r.max_ms)} мс\n   {esc(r.title[:150])}" for r in rows]
    return f"🐢 <b>Медленные операции</b>\n{SEP}\n{chr(10).join(lines) or EMPTY}\n{SEP}\n{_footer(total, page, per)}"


def error_view(r) -> str:
    if r is None:
        return EMPTY
    who = f" · игрок <code>{r.user_id}</code>" if r.user_id else ""
    head = f"🛠 <b>Ошибка #{r.id}</b> · {esc(r.process)} ×{n(r.hits)}{who}\nПервый раз {_ts(r.first_seen)}, последний {_ts(r.last_seen)}\n{esc(r.source)}\n{SEP}\n"
    return f"{head}<pre>{esc(r.detail[-(_MAX_TEXT - len(head) - 20):])}</pre>"


def error_item(r) -> dict:
    timing = f", до {n(r.max_ms)} мс" if r.max_ms else ""
    who = f" · игрок {r.user_id}" if r.user_id else ""
    return {"title": r.title, "sub": f"{r.process} ×{n(r.hits)}{timing}{who} · {r.source}", "lines": r.detail.splitlines() if r.detail else [], "created_at": r.last_seen}


def error_alert(entry) -> str:
    who = f"\nИгрок: <code>{entry.user_id}</code>" if entry.user_id else ""
    return f"🛠 <b>Новая ошибка</b> ({esc(entry.process)})\n<code>{esc(entry.title[:300])}</code>\n{esc(entry.source)}{who}\n\n<i>Подробности: /admin → Журналы → Ошибки</i>"


def player_header(uid: int) -> str:
    return f" · <code>{uid}</code>"
