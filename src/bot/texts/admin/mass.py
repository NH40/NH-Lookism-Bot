"""Админка/рассылка и массовая выдача: тексты."""
from bot.constant.admin.mass import (
    BROADCAST_CAPTION_LIMIT,
    BROADCAST_TEXT_LIMIT,
    FLT_ACTIVE_7D,
    FLT_ACTIVE_24H,
    FLT_ALL,
    FLT_CLAN,
    FLT_DONORS,
    FLT_NO_ROLE,
)

SEP = "━━━━━━━━━━━━━━━━━━"

FILTER_LABELS = {
    FLT_ALL: "👥 Все игроки",
    FLT_ACTIVE_24H: "🟢 Активные 24 ч",
    FLT_ACTIVE_7D: "📅 Активные 7 дней",
    FLT_DONORS: "💎 Донатеры",
    FLT_CLAN: "🏴 Участники клана",
    FLT_NO_ROLE: "🙂 Без админ-роли",
}

BTN_BROADCAST = "📢 Рассылка"
BTN_GRANT = "🎁 Массовая выдача"
BTN_BACK = "◀️ Назад"
BTN_SKIP = "⏭ Без кнопки"
BTN_SEND = "🚀 Отправить"
BTN_APPLY = "✅ Выдать всем"

MENU = (
    "📢 <b>Рассылка и массовая выдача</b>\n" + SEP + "\n"
    "Рассылка — текст, фото и кнопка выбранной аудитории.\n"
    "Массовая выдача — ресурс всей аудитории одним запросом.\n\n"
    "<i>Выбери действие.</i>"
)
PICK_FILTER = "{title}\n" + SEP + "\nКому?\n\n<i>Выбери аудиторию.</i>"
TITLE_BROADCAST = "📢 <b>Рассылка</b>"
TITLE_GRANT = "🎁 <b>Массовая выдача</b>"

CLAN_PROMPT = "🏴 Пришли <b>id или точное название клана</b>.\n\n<i>Участники этого клана станут аудиторией.</i>"
CLAN_NOT_FOUND = "⚠️ Клан не найден. Пришли id или точное название."

CONTENT_PROMPT = (
    "✍️ Пришли сообщение для рассылки.\n\n"
    f"• Текст с HTML-форматированием (до {BROADCAST_TEXT_LIMIT} симв.)\n"
    f"• или фото с подписью (до {BROADCAST_CAPTION_LIMIT} симв.)\n\n"
    "Аудитория: <b>{audience}</b> — {count} чел."
)
CONTENT_BAD = "⚠️ Нужен текст или фото с подписью, в пределах лимита Telegram. Пришли заново."
BUTTON_PROMPT = (
    "🔘 Пришли кнопку одной строкой:\n<code>текст | https://ссылка</code>\n\n"
    "<i>Или нажми «Без кнопки».</i>"
)
BUTTON_BAD = "⚠️ Формат: <code>текст | https://ссылка</code>. Пришли заново."
PREVIEW_CONFIRM = (
    "👆 Так увидят игроки.\n" + SEP + "\n"
    "Аудитория: <b>{audience}</b>\nПолучателей: <b>{count}</b>\n\n"
    "<i>Отправить? Рассылка идёт в фоне, по её окончании придёт отчёт.</i>"
)
BROADCAST_STARTED = "🚀 Рассылка запущена: {count} чел. Отчёт придёт по окончании."
BROADCAST_REPORT = (
    "📢 <b>Рассылка завершена</b>\n" + SEP + "\n"
    "Аудитория: <b>{audience}</b>\n✅ Отправлено: <b>{sent}</b>\n❌ Не доставлено: <b>{failed}</b>"
)
BROADCAST_FAILED = "⚠️ Рассылка прервалась с ошибкой. Смотри логи бота."

PICK_RESOURCE = "🎁 <b>Массовая выдача</b>\n" + SEP + "\nАудитория: <b>{audience}</b> — {count} чел.\n\n<i>Какой ресурс выдать?</i>"
AMOUNT_PROMPT = "🔢 Сколько <b>{resource}</b> выдать каждому? Пришли целое число &gt; 0 (до {limit})."
AMOUNT_BAD = "⚠️ Нужно целое число от 1 до {limit}. Пришли заново."
GRANT_CONFIRM = (
    "🎁 <b>Подтверди выдачу</b>\n" + SEP + "\n"
    "Аудитория: <b>{audience}</b>\nИгроков: <b>{count}</b>\nКаждому: <b>{amount}</b>\n\n"
    "<i>Действие необратимо.</i>"
)
GRANT_DONE = "✅ Выдано. Затронуто игроков: <b>{affected}</b>."
STATE_LOST_ALERT = "Данные сброшены — начни заново."
