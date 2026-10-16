"""Абсолютные карты — тексты."""
from __future__ import annotations

from bot.config.absolute import (
    ARKHANGEL_INCOME_SHARE,
    HASBULLA_SHOP_DISCOUNT,
    KUROPATKA_REVIVE,
    MANAGER_COINS_BURN,
    MARISE_CLONE,
    MARISE_CLONE_CAP,
    OGURCHIK_ATTACK,
    OGURCHIK_REACTIONS,
    TABASKO_SUPPRESS,
)
from bot.constant.absolute import (
    ABS_ARIAN,
    ABS_ARKHANGEL,
    ABS_HASBULLA,
    ABS_KUROPATKA,
    ABS_MANAGER,
    ABS_MARISE,
    ABS_NIKITA,
    ABS_OGURCHIK,
    ABS_QUANDE,
    ABS_STYLIST,
    ABS_TABASKO,
)

PERKS: dict[str, str] = {
    ABS_HASBULLA: f"Скидка {HASBULLA_SHOP_DISCOUNT:.0%} в магазине за NHCoin: контракты, зелья, ячейки.",
    ABS_KUROPATKA: f"Каждый павший статист с шансом {KUROPATKA_REVIVE:.0%} воскресает после боя.",
    ABS_MARISE: f"После атаки {MARISE_CLONE:.1%} выживших статистов клонируются (до {MARISE_CLONE_CAP:,} за бой).".replace(",", " "),
    ABS_TABASKO: f"Реакции противника срываются чаще: уклонение, блок, контратака и побег слабее на {TABASKO_SUPPRESS:.0%}.",
    ABS_OGURCHIK: f"«Плюс вайбик»: +{OGURCHIK_ATTACK:.0%} к атаке и +{OGURCHIK_REACTIONS * 100:.0f} п.п. ко всем реакциям.",
    ABS_QUANDE: "Без перка — просто редкая карта коллекции.",
    ABS_MANAGER: f"При любой атаке на тебя у напавшего сгорает {MANAGER_COINS_BURN:.0%} NHCoin.",
    ABS_NIKITA: "Шкала отчаяния: каждый твой павший — +1 мощи. Проиграл — шкала бьёт по армии противника, пока не кончится мощь.",
    ABS_ARKHANGEL: f"Раз в час приносит {ARKHANGEL_INCOME_SHARE:.0%} твоего часового дохода (пуш можно выключить в настройках).",
    ABS_STYLIST: "Позволяет выбрать перк любой абсолютной карты.",
    ABS_ARIAN: "Атакуя, блокирует абсолюты противника на 1 час (пишется в журнал боя).",
}
PERK_BLOCK = "\n♾ <b>Абсолют</b> — не воюет и не гибнет, действует, пока карта у тебя:\n<i>{perk}</i>"
STYLIST_PICKED = "\n🎨 Выбран перк: <b>{name}</b>"
STYLIST_PROMPT = "\n🎨 Выбери перк любой абсолютной карты:"
STYLIST_SET_ALERT = "Перк выбран: {name}"
BTN_STYLIST_PICK = "{mark}{name}"

JOURNAL_ARIAN = "♾ Ариан: абсолюты противника заблокированы на 1 ч"
JOURNAL_MANAGER = "♾ Менеджер: у напавшего сгорело {amount} NHCoin"
JOURNAL_MARISE = "♾ Marise: клонировано статистов — {count}"
PUSH_ARKHANGEL = "♾ Архангел принёс {amount} NHCoin — {share} часового дохода."
