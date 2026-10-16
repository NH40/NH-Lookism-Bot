"""Родословная (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

from bot.utils.formatting import format_number

from bot.constant.bloodline import (
    BLOODLINE_ELITE,
    BLOODLINE_GAPRYONG,
    BLOODLINE_HANSU,
    BLOODLINE_JINCHEOL,
    BLOODLINE_JINYEONG,
    BLOODLINE_KURODA,
    BLOODLINE_MUJIN,
    BLOODLINE_SAMDAK,
    BLOODLINE_SOPHIA,
    BLOODLINE_YAMAZAKI,
)

BLOODLINE_NAMES: dict[str, str] = {
    BLOODLINE_ELITE: "Элиты",
    BLOODLINE_MUJIN: "Муджина",
    BLOODLINE_JINYEONG: "Джинена",
    BLOODLINE_GAPRYONG: "Ким Гапрена",
    BLOODLINE_YAMAZAKI: "Ямадзаки",
    BLOODLINE_SAMDAK: "Самдака",
    BLOODLINE_SOPHIA: "Софии",
    BLOODLINE_KURODA: "Куроды",
    BLOODLINE_JINCHEOL: "Джинчоля",
    BLOODLINE_HANSU: "Хансу",
}
# Направления родословных — от пользователя (2026-10-02, `docs/design/development_systems.md`).
BLOODLINE_DESCRIPTIONS: dict[str, str] = {
    BLOODLINE_ELITE: "Бизнес: развитие, ускорение и рост дохода. Вербовка уникальных персонажей — тикеты, редкие уники, бесплатные крутки.",
    BLOODLINE_MUJIN: "Огромнейшая сила — пик физической силы: мощь каждого бойца, сокрушительные криты, пробитие.",
    BLOODLINE_JINYEONG: "Повышенные коэффициенты и дешёвый гений медицины. «Копирование» в бою: техника, родословная, а затем и путь противника. Усиливает путь Копирования.",
    BLOODLINE_GAPRYONG: "Огромные базовые характеристики — старт с ранга S. Техника Преодоления без учителя, усиление «трёх камней» Преодоления.",
    BLOODLINE_YAMAZAKI: "Чёрные кости — бойцы выдерживают больше, часть урона не доходит. Ультра инстинкт — вербовка, тренировки и крутка сами. Киокушинкай карате — пробитие.",
    BLOODLINE_SAMDAK: "Обучение: быстрее очки развития, быстрее задания мастерства, дешевле ранги, сильнее тренировки.",
    BLOODLINE_SOPHIA: "Читать противника, терпеть — и ударить: после потерь армия бьёт в разы сильнее, контрудары.",
    BLOODLINE_KURODA: "Ниндзя: скрытность в отчётах, на карте и от разведки, саботаж сильнее и тише, удар из тени.",
    BLOODLINE_JINCHEOL: "Военный: вербовка выше рангом и по двое, контракты статистов дешевле и дольше.",
    BLOODLINE_HANSU: "Хаос: бойцы действуют непредсказуемо — сокрушительные удары и сбитые реакции врага.",
}
SPECIAL_EFFECTS: dict[str, str] = {
    "copy_sources": "копирование в бою расширено",
    "copy_strength": "сила копирования +{p}",
    "copy_path_boost": "путь Копирования сильнее на {p}",
    "grant_overcome": "техника Преодоления — без учителя",
    "resonance_bonus": "резонанс «трёх камней» Преодоления сильнее на {p}",
}
DETAIL_SCREEN = (
    "🩸 <b>Родословная {name}</b> · ур. <b>{level}/10</b>\n"
    "<i>{description}</i>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{levels}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🩸 Капли крови: <b>{drops}</b> (за 🌀 пробуждение)\n"
    "{next_line}"
)
LEVEL_LINE_DONE = "✅ {n}. {effect}"
LEVEL_LINE_LOCKED = "🔒 {n}. {effect}"
NEXT_LEVEL_LINE = "⬆️ Следующий уровень — <b>{cost}</b> 🩸."
MAX_LEVEL_LINE = "🏆 <b>Родословная пробуждена полностью.</b>"
BTN_BLOODLINE_SCREEN = "🩸 Родословная"
BTN_LEVEL_UP = "⬆️ Пробудить · {cost} 🩸"
LEVEL_UP_ALERT = "Родословная: уровень {level}"
NOT_ENOUGH_BLOOD_ALERT = "Не хватает капель крови: нужно {cost}, у тебя {have}."
MAX_LEVEL_ALERT = "Родословная уже пробуждена полностью."
BLOODLINE_NO_DESCRIPTION = "Направление ветки раскроется в ближайших обновлениях."

CHOOSE_SCREEN = (
    "🩸 <b>Выбери родословную</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Родословная — твоя кровь на всю игру: выбираешь <b>один раз</b>, сменить потом нельзя. "
    "Её пробуждают каплями крови — они падают за пробуждение и активную игру.\n\n"
    "<i>Нажми на родословную, чтобы прочитать о ней:</i>"
)
BTN_BLOODLINE = "🩸 {name}"
VIEW_SCREEN = (
    "🩸 <b>Родословная {name}</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{description}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🎁 <b>Сразу:</b> {first}\n"
    "➕ Дальше — ещё 9 уровней за капли крови.\n\n"
    "⚠️ <i>Выбор — навсегда.</i>"
)
BTN_PICK = "✅ Выбрать навсегда"
BTN_BACK_TO_LIST = "◀️ К списку"
PICKED = "🩸 Теперь в тебе течёт кровь <b>{name}</b>."
ALREADY_CHOSEN_ALERT = "Родословная уже выбрана — сменить её нельзя."

# Строка профиля и блок экрана «Развитие».
PROFILE_LINE = "🩸 <b>Родословная:</b> {name} · ур. {level} · капли крови: {drops}"
PROFILE_LINE_NONE = "🩸 <b>Родословная:</b> не выбрана"


def bloodline_line(code: str | None, level: int, drops: int) -> str:
    """Строка родословной — общая для профиля и экрана «Развитие»."""
    if code is None:
        return PROFILE_LINE_NONE
    return PROFILE_LINE.format(name=BLOODLINE_NAMES[code], level=level, drops=format_number(drops))

BTN_BLOODLINE2_CHOOSE = "🩸 Вторая родословная"
BTN_BLOODLINE2_LEVEL_UP = "⬆️ Вторая · {cost} 🩸"
BTN_BLOODLINE2_OPEN = "🩸 Вторая: {name} · {level}/10"
SECOND_BODY_SUFFIX = " · второе тело"
BTN_BACK_TO_BLOODLINE = "◀️ К родословной"
CHOOSE2_SCREEN = (
    "🩸 <b>Вторая родословная</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Выбери родословную для второго тела. Выбор — навсегда."
)
SECOND_LINE = "\n🩸 <b>Вторая:</b> {name} · ур. <b>{level}/{max_level}</b>"
NO_SECOND_BODY_ALERT = "Второго тела у тебя нет."
PICKED_ALERT = "Вторая родословная: {name}"
