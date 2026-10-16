"""Экран «Профиль» — статистика, характеристики, мастерство, выбор уникальной техники/пути/родословной/гениальности/пробуждения, кнопка удаления банды (тексты)."""
from __future__ import annotations

from bot.constant.characteristic import (
    MASTERY_ENDURANCE,
    MASTERY_SPEED,
    MASTERY_STRENGTH,
    MASTERY_TECHNIQUE,
    POT_GANG_BOSS,
    POT_GEN_ZERO,
    POT_KING,
    POT_LEGEND,
    POT_MEMBER,
    POT_PEAK,
    POT_STRONG_KING,
    POT_WEAK_KING,
    STAT_AGILITY,
    STAT_ENDURANCE,
    STAT_SPEED,
    STAT_STRENGTH,
)
from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST, PHASE_GANG

PHASE_LABELS: dict[str, str] = {
    PHASE_GANG: "Банда",
    PHASE_CIRCLE: "Круг",
    PHASE_FIST: "Император (Кулак)",
}

PROFILE_CARD = (
    "👤 <b>Профиль</b>\n\n"
    "<b>Имя:</b> {display_name}\n"
    "<b>Username:</b> {username}\n"
    "<b>Банда:</b> {gang_name}\n"
    "<b>Клан:</b> {clan}\n"
    "<b>Страна:</b> {country} · <b>Город:</b> {city}\n"
    "<b>Фаза:</b> {phase_label}\n"
    "{bloodline_line}\n\n"
    "————— <b>СИЛА:</b> —————\n\n"
    "⚔️ <b>Мощь армии:</b> {army_power}\n"
    "🌐 <b>Влияние:</b> {influence} (районов: {districts})\n\n"
    "————— <b>РЕСУРСЫ:</b> —————\n\n"
    "🪙 <b>NHCoin:</b> {nh_coins}{pending_line}\n"
    "{tickets_line}\n{potions_block}\n"
    "————— <b>ХАРАКТЕРИСТИКИ:</b> —————\n"
    "<blockquote expandable>{stats_block}</blockquote>\n"
    "————— <b>МАСТЕРСТВО:</b> —————\n"
    "<blockquote expandable>{mastery_block}</blockquote>"
)
NO_CLAN = "нет клана"

# Действующие зелья (жалоба тестера 2026-10-10: «не видно зельки, не понятно, работают ли»).
POTIONS_BLOCK = "🧪 <b>Зелья действуют:</b>\n<blockquote expandable>{lines}</blockquote>\n"
POTION_LINE = "{name} {roman} — ещё {countdown}\n<i>{effect}</i>"

PENDING_LINE = " (+{pending} к сбору в 💼 Бизнесе)"

NOT_ONBOARDED ="Сначала пройди регистрацию — набери /start."


# --- Характеристики (raw-notes «Профиль») ---
STAT_LABELS: dict[str, str] = {
    STAT_STRENGTH: "💪 Сила",
    STAT_SPEED: "⚡ Скорость",
    STAT_ENDURANCE: "🛡 Выносливость",
    STAT_AGILITY: "🌀 Ловкость",
}
MASTERY_LABELS: dict[str, str] = {
    MASTERY_STRENGTH: "💪 Сила",
    MASTERY_SPEED: "⚡ Скорость",
    MASTERY_ENDURANCE: "🛡 Выносливость",
    MASTERY_TECHNIQUE: "🥋 Техника",
}
# Ступени мастерства (raw-notes «Профиль»: Стена → Трансцендентность → Мастерство).
MASTERY_TIER_LABELS: dict[int, str] = {0: "—", 1: "Стена", 2: "Трансцендентность", 3: "Мастерство"}
MASTERY_LINE = "{label}: {tier}"
MASTERY_LOCKED = "🔒 Задание «Преодоление стены» откроется, когда все характеристики дойдут до EXR."
MASTERY_OPEN_HINT = "🧱 Задания «Преодоление стены» — в 🥋 Мастерстве."
POTENTIAL_LABELS: dict[str, str] = {
    POT_MEMBER: "Член банды",
    POT_GANG_BOSS: "Глава группировки",
    POT_WEAK_KING: "Слабый король",
    POT_KING: "Король",
    POT_STRONG_KING: "Сильный король",
    POT_GEN_ZERO: "Нулевое поколение",
    POT_PEAK: "Вершина",
    POT_LEGEND: "Легенда",
}
DEV_POINTS_LINE = "🎯 <b>Очков развития:</b> {points}"
STAT_LINE = "{label}: <b>{rank}</b>{bonus}"
STRENGTH_BONUS = " (+{percent}% к мощи)"
POTENTIAL_LINE = "🧬 <b>Потенциал:</b> {potential}"

STATS_SCREEN = (
    "📊 <b>Характеристики</b>\n\n"
    "{lines}\n\n"
    "{effects}\n\n"
    "🎯 Очков развития: <b>{points}</b>\n"
    "Очки даёт 🧘 личная тренировка (раз в час), их число зависит от потенциала. "
    "Каждый следующий ранг стоит дороже."
)
STAT_SCREEN_LINE = "{label}: <b>{rank}</b> · след. ранг — {cost} оч."
STAT_SCREEN_LINE_MAX = "{label}: <b>{rank}</b> — максимум"
# На что влияет каждая характеристика — вместо цифр в скобках (пользователь 2026-10-02).
STAT_EFFECTS: dict[str, str] = {
    STAT_STRENGTH: "мощь всей армии",
    STAT_SPEED: "побег статистов из проигранной схватки и время соперника на принятие вызова",
    STAT_ENDURANCE: "поглощение урона и блок",
    STAT_AGILITY: "уклонение и шанс второй атаки без перерыва",
}
STAT_EFFECT_LINE = "{label} — {effect}"
BTN_STATS = "📊 Характеристики"
BTN_STAT_UP_ONE = "{label} +1"
BTN_STAT_UP_FIVE = "+5"
BTN_STAT_UP_MAX = "Макс"
BTN_PERSONAL_TRAINING = "🧘 Личная тренировка"

# --- popup (без HTML) ---
STAT_INVESTED = "{label}: +{ranks} → {rank} (−{cost} оч.)"
STAT_MAXED = "Эта характеристика уже на максимуме."
STAT_NOT_ENOUGH = "Не хватает очков: нужно {cost}, у тебя {points}. Очки даёт личная тренировка."
