"""Родословная Пеньгуана (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

BTN_PG = "💰 Пеньгуан: деньги — сила"
SCREEN = (
    "💰 <b>Пеньгуан</b> — игра через доход\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "📈 Доход зданий: <b>{income}</b>/ч · районов: <b>{districts}</b> · городов: <b>{cities}</b>\n"
    "💎 Богатство: <b>{points}</b> очк.\n"
    "{bonuses}"
    "━━━━━━━━━━━━━━━━━━\n"
    "{buffs}"
    "{extra}"
)
BONUS_ATTACK = "⚔️ +{p} к атаке от богатства\n"
BONUS_INFLUENCE = "🗣 +{p} к влиянию от богатства\n"
BONUS_INCOME = "🏙 +{p} к доходу от земель\n"
BUFF_NAMES = {"bribe": "🤝 Подкуп", "chest": "💰 Военная казна", "recruit": "🪖 Золотая вербовка"}
BUFF_EFFECTS = {"bribe": "реакции врага −{p}", "chest": "атака +{p}", "recruit": "бойцов за вербовку +{p}"}
BUFF_LINE = "{name} ({effect}, час): <b>{price}</b> 🪙{active}\n"
BUFF_ACTIVE = " · ✅ ещё {left}"
BTN_BUFF = "{name} · {price}"
BUYBACK_LINE = "\n⚰️ Выкуп павших последнего боя: <b>{units}</b> бойцов (мощь {power}) за <b>{price}</b> 🪙\n"
BTN_BUYBACK = "⚰️ Выкупить павших · {price}"
BUYOUT_LINE = "🏘 Выкуп района бота в своём городе: <b>{price}</b> 🪙{cd}\n"
BUYOUT_CD = " · через {left}"
BTN_BUYOUT = "🏘 Выкупить район · {price}"
BTN_BUILDER = "🧬 Конструктор статистов"
BTN_BACK = "◀️ Назад"

BUILDER = (
    "🧬 <b>Конструктор статистов</b>\n"
    "Собери статиста и купи в лагерь атаки — навсегда.\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Ранг: <b>{rank}</b> (до {ceiling})\n"
    "Уровень: <b>{level}</b>/{level_cap} · ⭐ <b>{stars}</b>\n"
    "Школа: <b>{school}</b>\n"
    "Мощь бойца: <b>{power}</b> · цена: <b>{price}</b> 🪙\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Сегодня куплено мощи: {bought} из {cap} · можно ещё <b>{left}</b> бойцов\n"
    "<i>Каждая покупка за сутки дороже предыдущей.</i>"
)
NO_SCHOOL = "без школы"
SCHOOL_LINE = "{name} · ур. {level}"
BTN_BUY = "Купить {n}"

BUFF_BOUGHT = "{name} — на час. Списано {price} NHCoin."
BOUGHT = "Куплено {n} статистов за {price} NHCoin."
BUYBACK_DONE = "Выкуплено {units} бойцов за {price} NHCoin."
BUYOUT_DONE = "Район {number} твой. Списано {price} NHCoin."
ERRORS = {
    "busy": "Обрабатываю…",
    "locked": "Откроется на следующих уровнях родословной.",
    "no_coins": "Не хватает NHCoin: нужно {0}.",
    "daily_cap": "Суточный лимит мощи исчерпан ({0}). Завтра — снова.",
    "no_fallen": "Нет павших для выкупа — окно 30 минут после боя.",
    "cooldown": "Следующий выкуп района — позже.",
    "no_district": "В твоём городе нет свободных районов ботов.",
    "phase": "Император и завоеватель города районы не выкупают.",
}
