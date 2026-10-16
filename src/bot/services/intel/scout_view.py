"""Отчёт разведки → строки «поле: значение» (простой текст, общий для бота и Mini App)."""
from __future__ import annotations

from datetime import datetime, timezone

from bot.constant.position_skill import (
    F_ATTACK_POWER,
    F_BATTLES,
    F_BLOODLINE,
    F_BUSINESS,
    F_CHALLENGES,
    F_CLAN,
    F_COOLDOWNS,
    F_DEFENSE_POWER,
    F_EMPTY_SLOTS,
    F_FORECAST,
    F_GENIUS,
    F_HEADCOUNT,
    F_LINEUP,
    F_PATH,
    F_POTIONS,
    F_RANKS,
    F_SKILLS,
    F_TECHNIQUE,
    F_TOP_SQUADS,
    F_WALLET,
    INTEL_FIELDS,
    SEEN_HIDDEN,
    SEEN_RANGE,
)
from bot.texts.bloodline import BLOODLINE_NAMES
from bot.texts.business import BUSINESS_NAMES
from bot.texts.card import POSITION_LABELS
from bot.texts.genius import GENIUS_NAMES
from bot.texts.position_skill import FIELD_LABELS, HIDDEN_VALUE, RANGE_VALUE
from bot.texts.potion import POTION_NAMES
from bot.texts.unique_path import PATH_NAMES
from bot.texts.unique_technique import TECHNIQUE_NAMES
from bot.utils.formatting import format_countdown, format_number

_NAMES = {F_BLOODLINE: BLOODLINE_NAMES, F_PATH: PATH_NAMES, F_TECHNIQUE: TECHNIQUE_NAMES, F_GENIUS: GENIUS_NAMES}


def _plain(text: str) -> str:
    head, _, tail = text.partition(" ")
    return tail if tail and not any(ch.isalnum() for ch in head) else text


def _num(v) -> str:
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
        return RANGE_VALUE.format(low=format_number(v[0]), high=format_number(v[1]))
    return format_number(v) if isinstance(v, (int, float)) else str(v)


def _value(field: str, value, seen: str) -> str:
    if value is None:
        return "—"
    if seen == SEEN_RANGE and isinstance(value, int) and field not in (F_HEADCOUNT, F_ATTACK_POWER, F_DEFENSE_POWER, F_COOLDOWNS):
        return f"{value} (подробности скрыты)"
    if field in (F_HEADCOUNT, F_ATTACK_POWER, F_DEFENSE_POWER):
        return _num(value)
    if field in _NAMES:
        code, level = value
        if not code:
            return "нет"
        name = _plain(_NAMES[field].get(code, code))
        return f"{name} · {level}" if level is not None else name
    if field == F_RANKS:
        return ", ".join(f"{r} ×{format_number(q)}" for r, q in value) or "—"
    if field == F_TOP_SQUADS:
        return ", ".join(f"{r} ×{format_number(q)}" for r, q in value) or "—"
    if field == F_LINEUP:
        return ", ".join(f"{_plain(POSITION_LABELS.get(p, p))}: {n}" for p, n in value) or "пусто"
    if field == F_EMPTY_SLOTS:
        return ", ".join(_plain(POSITION_LABELS.get(p, p)) for p in value) or "все заняты"
    if field == F_SKILLS:
        return ", ".join(n for _p, n in value) or "нет"
    if field == F_POTIONS:
        return ", ".join(f"{_plain(POTION_NAMES.get(k, k))} {t}" for k, t in value) or "нет"
    if field == F_WALLET:
        coins, per_min = value
        return f"{_num(coins)} NHCoin · {_num(per_min)}/мин"
    if field == F_BUSINESS:
        return ", ".join(f"{_plain(BUSINESS_NAMES.get(k, k))} ×{c}" for k, c in value) or "нет"
    if field == F_BATTLES:
        return " · ".join(x for _t, x in value) or "боёв не было"
    if field == F_COOLDOWNS:
        return "уже может" if not value else f"через {format_countdown(int(value))}"
    if field == F_CLAN:
        return f"{value[0]} ({value[1]})" if value else "без клана"
    if field == F_CHALLENGES:
        return "есть вызов" if value else "нет"
    if field == F_FORECAST:
        win, loss = value
        return f"шанс победы ~{round(win * 100)}%, потери ~{round(loss * 100)}%"
    return str(value)


def report_lines(payload: dict) -> list[tuple[str, str, str]]:
    """[(поле, подпись, значение)] в порядке `INTEL_FIELDS`; скрытые — «скрыто»."""
    out = []
    for field in INTEL_FIELDS:
        entry = payload.get(field)
        if not entry:
            continue
        seen = entry.get("seen")
        text = HIDDEN_VALUE if seen == SEEN_HIDDEN else _value(field, entry.get("value"), seen)
        out.append((field, FIELD_LABELS[field], text))
    return out


def ago(created_at: datetime) -> str:
    minutes = int((datetime.now(timezone.utc) - created_at).total_seconds() // 60)
    if minutes < 1:
        return "только что"
    if minutes < 60:
        return f"{minutes} мин назад"
    if minutes < 48 * 60:
        return f"{minutes // 60} ч назад"
    return f"{minutes // 1440} дн назад"
