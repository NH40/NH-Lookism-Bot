"""Уникальные техники и учителя (тексты). Popup-алерты — без HTML. Эффекты уровней
описываются из данных (`texts/development/effects.py`)."""
from __future__ import annotations

from bot.constant.unique_technique import (
    TECH_BEAST,
    TECH_BLADE_HANDS,
    TECH_CQC,
    TECH_INVISIBLE,
    TECH_KYOKUSHIN,
    TECH_MA_TAESU,
    TECH_MIDNIGHT,
    TECH_MUAY_THAI,
    TECH_NINJUTSU,
    TECH_ONE_STEP,
    TECH_OVERCOME,
    TECH_SEIRIM,
    TECH_TAEKWONDO,
)

TECHNIQUE_NAMES: dict[str, str] = {
    TECH_BEAST: "Звериный инстинкт",
    TECH_INVISIBLE: "Невидимые атаки",
    TECH_NINJUTSU: "Ниндзюцу",
    TECH_OVERCOME: "Преодоление",
    TECH_KYOKUSHIN: "Киокушинкай",
    TECH_TAEKWONDO: "Тхэквондо",
    TECH_MA_TAESU: "Кулак Ма Тэсу",
    TECH_ONE_STEP: "Удар одного шага",
    TECH_BLADE_HANDS: "Руки-лезвия",
    TECH_MUAY_THAI: "Муай-тай",
    TECH_MIDNIGHT: "Полуночный меч",
    TECH_CQC: "CQC",
    TECH_SEIRIM: "Сейрим",
}
TEACHER_NAMES: dict[str, str] = {
    TECH_BEAST: "Том Ли",
    TECH_INVISIBLE: "Элита",
    TECH_NINJUTSU: "Курода Рюхей",
    TECH_OVERCOME: "Джинран",
    TECH_KYOKUSHIN: "Кендзо Ямадзаки",
    TECH_TAEKWONDO: "Хансу",
    TECH_MA_TAESU: "Ма Тэсу",
    TECH_ONE_STEP: "Гансоп, лысый монах",
    TECH_BLADE_HANDS: "Джин Чан",
    TECH_MUAY_THAI: "Брэгдак",
    TECH_MIDNIGHT: "Банхо Ли",
    TECH_CQC: "Менеджер Ким",
    TECH_SEIRIM: "Сонджи Юк",
}
INFINITE_LINE = "\n♾ <b>Бесконечная техника:</b> одновременно {slots} (с активной). Выбраны: {selected}"
INFINITE_AUTO = "самые прокачанные"
SLOTS_FULL_ALERT = "Сейчас можно держать {limit} техник с активной. Шкала копирования откроет больше."
BTN_SELECT = "♾ Использовать вместе с активной"
BTN_UNSELECT = "♾ Убрать из активных"
TECHNIQUE_THEMES: dict[str, str] = {
    TECH_BEAST: "Рывки, хаос и дикость. Меньше блоков, больше атак, пробитие чужой брони.",
    TECH_INVISIBLE: "Скорость, уклонение и криты. В случайный момент враг получает удар из ниоткуда, каждый следующий сильнее: чем длиннее бой, тем их больше.",
    TECH_NINJUTSU: "Разведка, наблюдение, безопасность и шпионаж, а в бою шанс и сила крита, уклонение и долгое кровотечение.",
    TECH_OVERCOME: "Влияние. Статисты сильнее от влияния, часть урона гасится, часть павших выживает, а некоторые встают прямо в бою и бьют снова. С путём Преодоления и кровью Ким Гапрена — три камня одного человека.",
    TECH_KYOKUSHIN: "Болезненные удары: чем сильнее противник, тем сильнее бьёшь. Пробивает чужую прочность, держит свою, блоки и контратаки лучше.",
    TECH_TAEKWONDO: "Контратаки, уклонение и главное: один удар проходит сразу по нескольким бойцам, остаток урона от убитого переходит на следующего, реакции врага слабеют.",
    TECH_MA_TAESU: "Сокрушающий удар: одной рукой сносить камни.",
    TECH_ONE_STEP: "Один шаг и удар огромной силы: мастерство Скорости и Силы делают первый удар разрушительным.",
    TECH_BLADE_HANDS: "Руки как лезвия: режут броню и оставляют глубокие кровотечения.",
    TECH_MUAY_THAI: "Взрывной муай-тай: на время становишься намного сильнее.",
    TECH_MIDNIGHT: "Разгон: с каждым раундом боец успевает больше атак и бьёт сильнее, на максимуме 8 атак за ход. Раскрывается в длинном бою.",
    TECH_CQC: "Ближний бой спецназа: каждый убитый враг копит стаки, и чем дальше, тем быстрее они растут. Против толпы — ещё сильнее. Шкала CQC копится между боями: бой начинается уже со стаками.",
    TECH_SEIRIM: "Захваты и броски: сбивает стаки врага (отчаяние, CQC, разгон), хватает часть армии — она пропускает удар и летит на землю, первый раунд оглушает, враг медленнее.",
}
GAUGE_LINE = "\n📊 <b>Шкала {name}:</b> {value}/{cap} — стартовые стаки {start}"


def teacher_button_label(event) -> str:
    """Подпись метки учителя на карте (событие `teacher`)."""
    return f"🥋 {TEACHER_NAMES.get(event.code, event.code)} · {TECHNIQUE_NAMES.get(event.code, event.code)}"


TECHNIQUE_LINE = "🥋 <b>Уникальная техника:</b> {name} · ур. {level}"

TEACHER_SCREEN = (
    "🥋 <b>Учитель {teacher}</b> — «{technique}»\n"
    "<i>{theme}</i>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{body}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⏳ Уйдёт с карты через <b>{countdown}</b>"
)
TEACHER_OFFER = (
    "Законнекться — и получишь его квест. Выполнишь — техника твоя. Можно и проигнорировать.\n"
    "<i>⏳ Квест не сгорает, когда учитель уйдёт с карты — главное законнектиться, пока учитель "
    "здесь. Прогресс копится сколько угодно.</i>"
)
TEACHER_OWNED = "✅ Эта техника у тебя уже есть."
TEACHER_QUEST = "📜 <b>Квест учителя:</b>\n{tasks}"
TEACHER_QUEST_DONE = "\n\n🎁 Квест выполнен — забирай технику!"
BTN_CONNECT = "🤝 Законнектиться"
BTN_CLAIM = "🎁 Получить технику"
BTN_BACK_TO_MAP = "◀️ К карте"

TECHNIQUES_SCREEN = (
    "🥋 <b>Уникальные техники</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⚔️ Активна в бою: <b>{active}</b>\n"
    "🧩 Фрагменты УТ: <b>{fragments}</b> (падают с босса Джинена на 🗺 Карте)\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "📚 <b>Твои техники:</b>\n{owned}\n\n"
    "{quests}"
    "<i>Новые техники дают учителя — они появляются на 🗺 Карте.</i>"
)
NO_TECHNIQUES = "пока нет"
QUESTS_HEADER = "📜 <b>Квесты учителей:</b>\n"
QUEST_BLOCK = "«{technique}» ({teacher}):\n{tasks}\n\n"
OWNED_LINE = "{mark} {name} · ур. {level}"
MARK_ACTIVE = "✅"
MARK_OWNED = "▫️"

TECHNIQUE_DETAIL = (
    "🥋 <b>{name}</b> · ур. <b>{level}/10</b>{active}\n"
    "<i>{theme}</i>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{levels}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{next_line}"
)
DETAIL_ACTIVE = " · ✅ активна"
LEVEL_LINE_DONE = "✅ {n}. {effect}"
LEVEL_LINE_LOCKED = "🔒 {n}. {effect}"
NEXT_LEVEL_LINE = "⬆️ Следующий уровень — <b>{cost}</b> 🧩 УТ (у тебя {have})."
MAX_LEVEL_LINE = "🏆 <b>Максимальный уровень.</b>"
SPECIAL_EFFECTS: dict[str, str] = {
    "opening_per_mastery": "первый удар сильнее на {p} за каждую ступень мастерства Скорости и Силы",
}

BTN_TECHNIQUES = "🥋 Уникальные техники"
BTN_TECH_ITEM = "{mark} {name} · {level}"
BTN_CLAIM_QUEST = "🎁 {technique}"
BTN_LEVEL_UP = "🥋 Тренировка и уровень · {cost} 🧩"
BTN_ACTIVATE = "✅ Сделать активной"
BTN_BACK_TO_TECHNIQUES = "◀️ К техникам"

CONNECTED = "🤝 Ты законнектился с учителем <b>{teacher}</b>.\n━━━━━━━━━━━━━━━━━━\n📜 <b>Квест:</b>\n{tasks}\n━━━━━━━━━━━━━━━━━━\n<i>Квест не сгорает, когда учитель уйдёт с карты. Прогресс — в 📈 Развитии → 🥋 Уникальные техники.</i>"
CLAIMED = "🥋 Учитель {teacher} передал тебе технику <b>{technique}</b>!"
TEACHER_GONE_ALERT = "Учитель уже ушёл с карты."
TECHNIQUE_OWNED_ALERT = "Эта техника у тебя уже есть."
QUEST_ACTIVE_ALERT = "Квест этого учителя у тебя уже идёт."
QUEST_NOT_DONE_ALERT = "Квест учителя ещё не выполнен."
ACTIVATED_ALERT = "Активна: {name}"
LEVEL_UP_ALERT = "{name}: уровень {level}"
NOT_ENOUGH_ALERT = "Не хватает: нужно {cost} фрагментов УТ, у тебя {have}."
MAX_LEVEL_ALERT = "Уже максимальный уровень."
SWAP_COOLDOWN_ALERT = "Переключать технику можно раз в 15 минут — ещё {countdown}."
NOT_OWNED_ALERT = "Этой техники у тебя нет."
PUSH_TEACHER = (
    "🥋 На карте появился учитель <b>{teacher}</b> — на {duration}.\n"
    "Его техника: «{technique}». Законнекться на 🗺 Карте и пройди его квест."
)
