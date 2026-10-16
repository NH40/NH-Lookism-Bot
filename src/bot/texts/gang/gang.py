"""Банда игрока — название, состав (9 позиций), статисты (лагеря) (тексты)."""
from __future__ import annotations

from bot.config.game import GANG_NAME_MAX_LENGTH, GANG_NAME_MIN_LENGTH

NAME_PROMPT = "🏴 Придумай название для своей банды (от {min} до {max} символов):".format(
    min=GANG_NAME_MIN_LENGTH, max=GANG_NAME_MAX_LENGTH
)

NAME_TOO_SHORT = f"Слишком коротко — минимум {GANG_NAME_MIN_LENGTH} символа. Попробуй ещё раз:"
NAME_TOO_LONG = f"Слишком длинно — максимум {GANG_NAME_MAX_LENGTH} символов. Попробуй ещё раз:"

NAME_CONFIRMED = "✅ Банда «{name}» создана!"

GANG_SCREEN = (
    "🏴 <b>Банда «{name}»</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⚔️ Лагерь атаки: <b>{attack_quantity}</b> статистов, мощь <b>{attack_power}</b>\n"
    "🛡 Лагерь защиты: <b>{defense_quantity}</b> статистов, мощь <b>{defense_power}</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Нападаешь ты только лагерем атаки. Если на твой район нападут, а ты не примешь "
    "бой, — район держит лагерь защиты.</i>\n\n"
    "<i>Быстро перевести долю ВСЕЙ армии — кнопки ниже. Собрать лагеря вручную, по "
    "отрядам и точным числом, — «⚙️ Настроить отряды».</i>"
)

BTN_TO_DEFENSE = "⚔️→🛡 {label}"
BTN_TO_ATTACK = "🛡→⚔️ {label}"
PERCENT_ALL_LABEL = "всех"
BTN_SQUADS = "⚙️ Настроить отряды"
BTN_BACK_TO_GANG = "◀️ К банде"
BTN_BACK_TO_SQUADS = "◀️ К отрядам"
BTN_BACK_TO_SQUAD = "◀️ К отряду"

# --- ручная сборка лагерей по отрядам ---
SQUADS_HEADER = (
    "⚙️ <b>Отряды</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⚔️ Атака: <b>{attack_quantity}</b> (мощь {attack_power}) · 🛡 Защита: <b>{defense_quantity}</b> "
    "(мощь {defense_power})\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Отряд — статисты одного ранга, звёзд и уровня тренировки. Сильнейшие — сверху.</i>\n"
    "👇 Выбери отряд, чтобы расставить его бойцов по лагерям:"
)
SQUADS_EMPTY = "⚙️ <b>Отряды</b>\n━━━━━━━━━━━━━━━━━━\nСтатистов пока нет — сначала заверби хотя бы одного."
SQUAD_BTN = "{title} — ⚔️ {attack} · 🛡 {defense}"

SQUAD_SCREEN = (
    "🧩 <b>Отряд {title}</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "💪 Мощь одного бойца: <b>{unit_power}</b>\n"
    "⚔️ В атаке: <b>{attack}</b>\n"
    "🛡 В защите: <b>{defense}</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Сколько бойцов этого отряда перевести?</i>"
)
SQUAD_GONE = "Этого отряда больше нет — бойцы могли погибнуть в бою или пройти тренировку."
AMOUNT_HALF_LABEL = "половину"
BTN_SQUAD_CUSTOM_TO_DEFENSE = "⚔️→🛡 ✏️ своё"
BTN_SQUAD_CUSTOM_TO_ATTACK = "🛡→⚔️ ✏️ своё"

SQUAD_AMOUNT_PROMPT = (
    "✏️ Сколько бойцов отряда {title} перевести {direction}? Сейчас там: {available}.\n"
    "Пришли число."
)
DIRECTION_TO_DEFENSE = "из атаки в защиту"
DIRECTION_TO_ATTACK = "из защиты в атаку"
SQUAD_AMOUNT_INVALID = "Нужно целое положительное число. Попробуй ещё раз:"
SQUAD_MOVED_MESSAGE = "✅ Переведено бойцов: {moved}"
SQUAD_NOTHING_MOVED_MESSAGE = "В этом лагере у отряда не осталось бойцов — переводить нечего."


def squad_title(rank: str, stars: int, training_level: int, school: str = "", school_level: int = 0) -> str:
    """Короткое имя отряда: ранг, звёзды пробуждения, уровень тренировки и школа учителя —
    только ненулевые, чтобы свежезавербованный отряд читался просто как «D»."""
    from bot.constant.extra import CONTRACT_SQUAD
    from bot.texts.school import SCHOOL_NAMES, SCHOOL_TAG

    if school == CONTRACT_SQUAD:
        return f"📜 {rank} · контракт"
    title = rank
    if stars:
        title += f" ⭐{stars}"
    if training_level:
        title += f" ур.{training_level}"
    if school:
        title += SCHOOL_TAG.format(name=SCHOOL_NAMES.get(school, school), level=school_level)
    return title


# --- popup (без HTML) ---
CAMP_MOVED = "Переведено статистов: {moved}"
CAMP_NOTHING_TO_MOVE = "Нечего переводить — в этом лагере нет статистов (или их слишком мало для этой доли)."
SQUAD_NOTHING_TO_MOVE = "Нечего переводить — в этом лагере у отряда нет бойцов (или их слишком мало для этой доли)."

# --- состав отряда (9 позиций уников) ---
BTN_COLLECTION = "🃏 Уники"
BTN_LINEUP = "🏴 Состав"
BTN_BACK_TO_LINEUP = "◀️ К составу"
LINEUP_HEADER = (
    "🏴 <b>Состав отряда</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{lines}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Карта на позиции не сражается и не гибнет — работает навыком позиции. Одна копия — "
    "одна позиция. Нажми на позицию, чтобы поставить или снять карту.</i>"
)
LINEUP_LINE = "{position}: {card}"
LINEUP_EMPTY_SLOT = "—"
POSITION_BTN = "{position}: {card}"
POSITION_SCREEN = (
    "📌 <b>{position}</b>\n"
    "<i>{description}</i>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🃏 Сейчас: <b>{current}</b>\n"
    "{skills}\n"
    "{choices}"
)
POSITION_CHOICES = "Подходящие карты (есть свободная копия):"
POSITION_NO_CHOICES = "Подходящих карт со свободной копией нет — крути уников в 🎯 Вербовке."
BTN_POSITION_SET = "{label} (свободно: {free})"
BTN_POSITION_MOVE = "{label} (переедет с поз. «{from_pos}»)"
BTN_POSITION_CLEAR = "❌ Снять {card}"

# --- popup (без HTML) ---
POSITION_SET = "{card} — теперь {position}"
POSITION_SET_REPLACED = "{card} — теперь {position}. {old} вернулся в армию."
POSITION_CLEARED = "{card} снят с позиции и вернулся в армию."
POSITION_ALREADY_EMPTY = "Позиция уже пуста."
POSITION_NO_FREE_COPY = "Свободных копий этой карты нет."
POSITION_NOT_ALLOWED = "Эта карта не может стоять на этой позиции."


# --- удаление банды (полный сброс) ---
BTN_DELETE_GANG = "🗑 Удалить банду"
DELETE_CONFIRM_SCREEN = (
    "⚠️ <b>Удалить банду?</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🗑 Сбросится весь прогресс: банда, районы и бизнес на них, статисты, уникальные персонажи, "
    "характеристики, мастерство, NHCoin. Ты заново выберешь страну и город.\n\n"
    "🧬 Останутся: потенциал (а позже — пробуждение, родословная и талант).\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Это необратимо. Кнопка подтверждения действует {seconds} секунд.</i>"
)
BTN_DELETE_CONFIRM = "⚠️ Да, удалить всё"
DELETE_DONE = "🗑 Банда удалена. Начнём заново — выбери страну."
# popup (без HTML)
DELETE_EXPIRED = "Подтверждение истекло — открой удаление банды ещё раз."
