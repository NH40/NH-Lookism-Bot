"""Уникальные техники (константы). Дизайн — `docs/design/development_systems.md`."""
from __future__ import annotations

TECH_BEAST = "beast"  # Звериный инстинкт — Том Ли
TECH_INVISIBLE = "invisible"  # Невидимые атаки — Элита
TECH_NINJUTSU = "ninjutsu"  # Ниндзюцу — Курода Рюхей
TECH_OVERCOME = "overcome"  # Преодоление — Джинран
TECH_KYOKUSHIN = "kyokushin"  # Киокушинкай
TECH_TAEKWONDO = "taekwondo"  # Тхэквондо — Хансу
TECH_MA_TAESU = "ma_taesu"  # Техника Ма Тэсу
TECH_ONE_STEP = "one_step"  # Одного шага — Гансоп
TECH_BLADE_HANDS = "blade_hands"  # Руки-лезвия — Джин Чан
TECH_MUAY_THAI = "muay_thai"  # Муай-тай — Брэгдак
TECH_MIDNIGHT = "midnight"  # Полуночного меча
TECHNIQUES: tuple[str, ...] = (
    TECH_BEAST, TECH_INVISIBLE, TECH_NINJUTSU, TECH_OVERCOME, TECH_KYOKUSHIN, TECH_TAEKWONDO,
    TECH_MA_TAESU, TECH_ONE_STEP, TECH_BLADE_HANDS, TECH_MUAY_THAI, TECH_MIDNIGHT,
)

CB_TECH_OPEN = "tech:open"
CB_TECH_VIEW_PREFIX = "tech:view:"
CB_TECH_ACTIVATE_PREFIX = "tech:act:"
CB_TECH_LEVEL_UP_PREFIX = "tech:up:"
CB_TECH_CLAIM_PREFIX = "tech:claim:"
"""f"{CB_TECH_CLAIM_PREFIX}{code}" — забрать технику за выполненный квест учителя."""
