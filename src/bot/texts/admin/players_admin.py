"""Админка: действия над игроком (выдача, развитие, наказания) — тексты."""
from __future__ import annotations

SEP = "━━━━━━━━━━━━━━━━━━"
BTN_BACK = "◀️ Назад"
BTN_YES = "✅ Да, подтверждаю"
BTN_NO = "❌ Отмена"
NOT_FOUND_ALERT = "Игрок не найден."
TARGET_IS_STAFF_ALERT = "Нельзя: у игрока есть роль в админке — сначала снимите её в разделе «Роли»."
TARGET_IS_SELF_ALERT = "Нельзя применить к самому себе."
NOTICE = "✅ <i>{text}</i>\n\n"

# --- Выдача ---
GIVE_MENU = f"💰 <b>Выдать / забрать</b> · {{name}}\n{SEP}\nВыберите, что выдать (отрицательное число — забрать, ниже нуля не уйдёт).\n\n<i>Всё пишется в журнал.</i>"
BTN_GIVE_RESOURCES = "🪙 Ресурсы"
BTN_GIVE_STATIST = "👥 Статисты"
BTN_GIVE_CARD = "🃏 Уник-карта"
BTN_GIVE_SCROLLS = "📜 Свитки пропуска"
BTN_GIVE_XP = "🎫 Опыт Battle Pass"
GIVE_RES_LIST = f"🪙 <b>Ресурсы</b> · {{name}}\n{SEP}\nВыберите ресурс.\n\n{{balances}}"
GIVE_RES_PROMPT = "🪙 <b>{label}</b> · {name}\nСейчас: <b>{balance}</b>\n\nВведите число (например <code>500</code> или <code>-200</code>)."
GIVE_STATIST_PROMPT = (
    "👥 <b>Статисты</b> · {name}\n\nВведите: <code>ранг звёзды количество</code>, например <code>C 1 500</code>.\n"
    "Отрицательное количество — забрать. Ранги: {ranks}"
)
GIVE_CARD_PROMPT = "🃏 <b>Уник-карта</b> · {name}\n\nВведите: <code>код_карты количество</code>, например <code>arim_crewhead 1</code>. Отрицательное — забрать."
GIVE_SCROLLS_PROMPT = "📜 <b>Свитки пропуска</b> · {name}\nСейчас: <b>{balance}</b>\n\nВведите число (отрицательное — забрать)."
GIVE_XP_PROMPT = "🎫 <b>Опыт Battle Pass</b> · {name}\nСейчас: <b>{balance}</b>\n\nВведите число опыта (отрицательное — забрать; дневной буст не применяется)."
GIVE_BAD_NUMBER = "⚠️ Нужно целое число, не ноль."
GIVE_BAD_STATIST = "⚠️ Формат: <code>ранг звёзды количество</code>. Известные ранги: {ranks}"
GIVE_BAD_CARD = "⚠️ Не нашёл карту <code>{code}</code>.{hint}"
GIVE_CARD_HINT = " Похожие: {codes}"
GIVE_NOT_ENOUGH = "⚠️ У игрока нет столько ({have})."
DONE_RESOURCE = "{label}: {sign}{amount} (стало {balance})"
DONE_STATIST = "Статисты {rank}{stars}★: {sign}{amount}"
DONE_CARD = "Карта {name}: {sign}{amount}"
DONE_SCROLLS = "Свитки пропуска: {sign}{amount} (стало {balance})"
DONE_XP = "Опыт Battle Pass: {sign}{amount} (стало {balance})"

# --- Развитие ---
DEV_MENU = f"🧬 <b>Развитие</b> · {{name}}\n{SEP}\n{{summary}}\n<i>Выберите систему.</i>"
BTN_DEV_PATHS = "🛤 Пути"
BTN_DEV_TECHS = "🥋 Техники"
BTN_DEV_GENIUSES = "🧠 Гениальности"
BTN_DEV_BLOOD1 = "🩸 Родословная"
BTN_DEV_BLOOD2 = "🩸 Родословная 2"
BTN_DEV_MISC = "⚙️ Прочее"
DEV_KIND_TITLES = {"path": "Пути", "tech": "Уникальные техники", "gen": "Гениальности"}
DEV_LIST = f"🧬 <b>{{title}}</b> · {{name}}\n{SEP}\n★ — активный. Число — уровень.\n<i>Выберите, что менять.</i>"
DEV_ITEM = f"🧬 <b>{{title}}</b> · {{name}}\n{SEP}\nСтатус: <b>{{status}}</b>\n\n<i>Выберите уровень (1–{{max}}) — выдаст, если нет.</i>"
STATUS_NOT_OWNED = "нет у игрока"
STATUS_OWNED = "уровень {level}{active}"
STATUS_ACTIVE = ", активен"
BTN_LEVEL_TAKE = "🗑 Забрать"
BTN_MAKE_ACTIVE = "★ Сделать активным"
DEV_BLOOD = f"🩸 <b>Родословная {{slot}}</b> · {{name}}\n{SEP}\nСейчас: <b>{{current}}</b>\n\n<i>Выберите родословную или уровень.</i>"
BTN_BLOOD_NONE = "🗑 Убрать"
DEV_MISC = f"⚙️ <b>Прочее</b> · {{name}}\n{SEP}\nВторое тело: <b>{{body}}</b>\nПремиум-пасс сезона: <b>{{premium}}</b>\nПробуждение: <b>{{awakening}}</b>\nПотенциал: <b>{{potential}}</b>\nХарактеристики: {{stats}}"
BTN_TOGGLE_BODY = "👥 Второе тело: {state}"
BTN_TOGGLE_PASS = "🎫 Премиум-пасс: {state}"
BTN_AWAKENING = "⚡ Пробуждение"
BTN_POTENTIAL = "💠 Потенциал"
BTN_STATS = "💪 Характеристики"
STATE_ON = "вкл"
STATE_OFF = "выкл"
YES = "да"
NO = "нет"
DEV_AWAKEN = f"⚡ <b>Пробуждение</b> · {{name}}\n{SEP}\nСейчас: <b>{{current}}</b>. Выберите этап (0 — без пробуждения)."
DEV_POTENTIAL = f"💠 <b>Потенциал</b> · {{name}}\n{SEP}\nСейчас: <b>{{current}}</b>."
DEV_STATS = f"💪 <b>Характеристики</b> · {{name}}\n{SEP}\n{{stats}}\n\n<i>Выберите характеристику.</i>"
DEV_RANK_PROMPT = "💪 <b>{stat}</b> · {name}\nСейчас: <b>{current}</b>\n\nВведите ранг: {ranks}"
DEV_BAD_RANK = "⚠️ Нет такого ранга. Доступные: {ranks}"
STAT_NAMES = {"strength": "Сила", "speed": "Скорость", "endurance": "Выносливость", "agility": "Ловкость"}
DONE_LEVEL = "{title}: {item} → уровень {level}"
DONE_TAKEN = "{title}: {item} забран"
DONE_ACTIVE = "{title}: {item} активен"
NOT_OWNED_ALERT = "Сначала выдайте (выберите уровень)."
DONE_BLOOD = "Родословная {slot}: {value}"
DONE_BODY = "Второе тело: {state}"
DONE_PASS = "Премиум-пасс: {state}"
DONE_AWAKEN = "Пробуждение: {value}"
DONE_POTENTIAL = "Потенциал: {value}"
DONE_STAT = "{stat}: ранг {rank}"

# --- Наказания ---
PUNISH_MENU = f"⛔️ <b>Наказания и сброс</b> · {{name}}\n{SEP}\nСтатус: <b>{{status}}</b>\n\n<i>Необратимые действия просят подтверждение.</i>"
STATUS_BANNED = "в бане{until}"
STATUS_OK = "без ограничений"
BTN_BAN = "🔨 Забанить"
BTN_UNBAN = "🕊 Разбанить"
BTN_COOLDOWNS = "⏱ Сбросить кулдауны"
BTN_RESET = "♻️ Сбросить прогресс"
BTN_DELETE = "🗑 Удалить аккаунт"
BAN_DURATION_TITLES = {"1h": "1 час", "1d": "1 день", "7d": "7 дней", "30d": "30 дней", "forever": "Навсегда"}
BAN_CHOOSE = f"🔨 <b>Бан</b> · {{name}}\n{SEP}\nВыберите срок."
BAN_REASON_PROMPT = "🔨 <b>Бан</b> · {name} · {duration}\n\nВведите причину (до {max} символов) или нажмите «Без причины»."
BTN_NO_REASON = "Без причины"
BAN_REASON_TOO_LONG = "⚠️ Слишком длинно (максимум {max})."
DONE_BAN = "Бан выдан: {duration}"
DONE_UNBAN = "Бан снят"
DONE_COOLDOWNS = "Кулдауны сброшены ({count})"
DONE_RESET = "Прогресс игрока сброшен"
NOT_BANNED_ALERT = "Игрок не в бане."
PLAYER_BANNED = "⛔️ <b>Вы заблокированы.</b>\nСрок: {duration}.{reason}"
PLAYER_BANNED_REASON = "\nПричина: {reason}"
PLAYER_UNBANNED = "🕊 <b>Блокировка снята.</b> С возвращением!"
RESET_CONFIRM = f"♻️ <b>Сбросить прогресс</b> · {{name}}\n{SEP}\nИгрок вернётся к началу (как после удаления банды): страна, город, банда, статисты, пути, техники, здания. Потенциал, пробуждение, родословная и гениальности остаются.\n\n<b>Подтвердить?</b>"
DELETE_CONFIRM = f"🗑 <b>Удалить аккаунт</b> · {{name}}\n{SEP}\nИгрок и ВСЕ его данные будут удалены безвозвратно.\n\n<b>Подтвердить?</b>"
DELETE_OWNER_BLOCKED = "Игрок — владелец клана с другими участниками ({members}). Передайте клан или распустите его."
DELETE_FAILED = "Не удалось удалить: остались связанные данные ({reason})."
DELETED = "🗑 <b>Аккаунт удалён.</b>\nИгрок <code>{id}</code> стёрт."

# --- Каталоги систем развития (код → название), порядок как в constant ---
from bot.constant.bloodline import BLOODLINES  # noqa: E402
from bot.constant.genius import GENIUSES  # noqa: E402
from bot.constant.unique_path import PATHS  # noqa: E402
from bot.constant.unique_technique import TECHNIQUES  # noqa: E402
from bot.texts.bloodline import BLOODLINE_NAMES  # noqa: E402
from bot.texts.genius import GENIUS_NAMES  # noqa: E402
from bot.texts.unique_path import PATH_NAMES  # noqa: E402
from bot.texts.unique_technique import TECHNIQUE_NAMES  # noqa: E402

DEV_CODES: dict[str, tuple[str, ...]] = {"path": PATHS, "tech": TECHNIQUES, "gen": GENIUSES}
DEV_NAMES: dict[str, dict[str, str]] = {"path": PATH_NAMES, "tech": TECHNIQUE_NAMES, "gen": GENIUS_NAMES}
BLOODLINE_CODES = BLOODLINES
BLOODLINE_TITLES = BLOODLINE_NAMES

# --- статисты кнопками (2026-10-13) ---
AST_SCREEN = (
    "👥 <b>Статисты</b> · {name}\n━━━━━━━━━━━━━━━━━━\n"
    "Всего: <b>{total}</b> · ⚔️ {attack} · 🛡 {defense}\n━━━━━━━━━━━━━━━━━━\n"
    "{squads}\n\n<i>Отряд — забрать долю или добавить. «➕ Выдать» — ранг и количество кнопками.</i>"
)
AST_NONE = "<i>Статистов нет.</i>"
AST_SQUAD_LINE = "▫️ {title} — {qty}"
AST_MORE = "\n<i>…и ещё {n} отрядов (показаны сильнейшие)</i>"
AST_SQUAD_SCREEN = "👥 <b>Отряд {title}</b> · {name}\n━━━━━━━━━━━━━━━━━━\nВсего: <b>{total}</b> (⚔️ {attack} · 🛡 {defense})"
AST_RANKS_SCREEN = "➕ <b>Выдать статистов</b> · {name}\nВыбери ранг (звёзды 0; другие звёзды — «✏️ Вручную»):"
AST_AMOUNT_SCREEN = "➕ <b>Выдать {rank}</b> · {name}\nСколько?"
AST_WIPE_ASK = "🗑 <b>Забрать ВСЕХ статистов</b> у {name}?\nСейчас у игрока: <b>{total}</b>. Действие необратимо."
BTN_AST_SQUAD = "{title} · {qty}"
BTN_AST_TAKE = "➖ {label}"
BTN_AST_ADD = "➕ {n}"
BTN_AST_GIVE = "➕ Выдать"
BTN_AST_MANUAL = "✏️ Вручную"
BTN_AST_WIPE = "🗑 Забрать всех"
BTN_AST_WIPE_YES = "🗑 Да, забрать всех"
AST_ALL = "все"
AST_DONE_TAKE = "Забрано {n} × {title}"
AST_DONE_ADD = "Выдано {n} × {title}"
AST_DONE_WIPE = "Забрано всех статистов: {n}"
AST_NOTHING = "Нечего забирать."
# --- фаза (2026-10-13) ---
BTN_PHASE = "{mark}{label}"
PHASE_DONE = "Фаза игрока: {label}"
PHASE_EMPEROR_TAKEN = "В этой стране уже есть император — сначала переведи его."
