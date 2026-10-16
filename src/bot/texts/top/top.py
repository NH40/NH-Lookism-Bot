"""Топ игроков/кланов и список игроков (тексты)."""
from __future__ import annotations

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

TOP_PLAYERS_SCREEN = (
    "🏆 <b>Топ игроков</b> — по мощи армии\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{rows}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "📍 Твоё место: <b>{my_place}</b> · ⚔️ {my_power}\n"
    "{season_line}"
    "<i>Награды — по итогу сезона (раз в месяц) и при вайпе. Мощь обновляется раз в 10 минут.</i>"
)
TOP_CLANS_SCREEN = (
    "🏯 <b>Топ кланов</b> — по землям\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{rows}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{season_line}"
    "<i>Награда — каждому участнику клана: топ-3 — донат-коины, 4–5 места — NHCoin и тикеты.</i>"
)
SEASON_LINE = "⏳ Итог сезона через <b>{countdown}</b>\n"
PLAYER_ROW = "{medal} <b>{name}</b> — ⚔️ {power}{reward}"
CLAN_ROW = "{medal} <b>{name}</b> — 🗺 {lands} · 👥 {members}{reward}"
REWARD_SUFFIX = "\n      🎁 {reward}"
EMPTY_ROWS = "<i>Пока пусто.</i>"
NOT_IN_TOP = "—"

PLAYERS_SCREEN = (
    "👥 <b>Все игроки</b> — {total}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{rows}"
)
PLAYERS_ROW = "{place}. <b>{name}</b> · {phase} · ⚔️ {power}{clan}"
PLAYERS_CLAN = " · 🏯 {clan}"

BTN_TAB_PLAYERS = "🏆 Игроки"
BTN_TAB_CLANS = "🏯 Кланы"
BTN_ALL_PLAYERS = "👥 Все игроки"
BTN_TO_TOP = "🏆 Топ"

PUSH_PLAYER_REWARD = "🏆 <b>Итоги сезона!</b>\nТы на <b>{place}-м месте</b> топа игроков. Награда: {reward}."
PUSH_CLAN_REWARD = "🏯 <b>Итоги сезона!</b>\nТвой клан <b>{clan}</b> на <b>{place}-м месте</b>. Награда тебе: {reward}."


def reward_text(donate: int, coins: int, tickets: int) -> str:
    """«350 💎 + 60 000 🪙 + 8 🎟» — только ненулевые части; пусто — нет награды."""
    parts = []
    if donate:
        parts.append(f"{donate:,} 💎".replace(",", " "))
    if coins:
        parts.append(f"{coins:,} 🪙".replace(",", " "))
    if tickets:
        parts.append(f"{tickets} 🎟")
    return " + ".join(parts)
