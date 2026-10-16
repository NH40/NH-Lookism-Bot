"""Пуши «готово» по окончании КД (тексты)."""
from __future__ import annotations

from bot.constant.cooldown import CD_BATTLE, CD_EXTRAS, CD_PERSONAL

PUSH_READY: dict[str, str] = {
    CD_BATTLE: "⚔️ <b>Можно атаковать!</b> Кулдаун сражений прошёл — банда готова к бою.",
    CD_PERSONAL: "🧘 <b>Личная тренировка готова!</b> Можно снова тренироваться и получать очки развития.",
    CD_EXTRAS: "🏋 <b>Тренировка статистов готова!</b> Отправь армию на новую тренировку.",
}
PUSH_MUTE_HINT = "\n\n<i>Такие уведомления о готовности можно отключить: ⚙️ Настройки → 🔔 Уведомления.</i>"
BTN_TO_SETTINGS = "🔕 Отключить"
BTN_TO_MAP = "🗺 На карту"
BTN_TO_TRAINING = "🏋 К тренировкам"
