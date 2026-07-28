"""Постоянное меню быстрого доступа — системная клавиатура Telegram рядом с
полем ввода (ReplyKeyboardMarkup), в дополнение к обычным inline-кнопкам.
Не заменяет inline-хаб главного меню — просто быстрый доступ к самым частым
разделам с любого экрана."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

QUICK_MENU_LABELS = [
    "👤 Профиль", "⚔️ Атака",
    "⚔️ Рейд", "👹 Боссы",
    "🗺 Походы", "🏢 Бизнес",
    "🏦 Банк", "🛒 Магазин",
    "🏪 Биржа", "🏛 Аукцион",
    "👥 Группировка", "🃏 Колода",
    "🏆 Титулы", "⚡ Навыки",
    "🏋 Тренировка", "🏯 Кланы",
    "📋 Задания", "⚙️ Прочее",
]


def quick_menu_kb() -> ReplyKeyboardMarkup:
    rows = [QUICK_MENU_LABELS[i:i + 2] for i in range(0, len(QUICK_MENU_LABELS), 2)]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in rows],
        resize_keyboard=True,
        # is_persistent=True по докам Bot API "requests clients to always
        # show the keyboard" — именно это ОТКЛЮЧАЕТ нативную кнопку
        # сворачивания/разворачивания (клавиатура жёстко закреплена и её
        # некуда прятать). С is_persistent=False (по умолчанию) Telegram
        # возвращает обычный переключатель-клавиатуру рядом с полем ввода.
        is_persistent=False,
        input_field_placeholder="Меню",
    )
