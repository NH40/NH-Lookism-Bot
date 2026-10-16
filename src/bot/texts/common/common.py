"""Общее reply-меню бота (тексты)."""
from __future__ import annotations

from bot.utils.formatting import format_number

SECTION_IN_DEVELOPMENT = "🚧 Раздел в разработке — скоро."

NO_EXTRAS = "Статистов пока нет."

BTN_BACK = "◀️ Назад"
BTN_BACK_TO_PROFILE = "◀️ В профиль"


def render_army_block(
    *,
    total_quantity: int,
    total_power: int,
    attack_quantity: int,
    defense_quantity: int,
    by_rank: list[tuple[str, int]],
    cards_quantity: int = 0,
) -> str:
    """Общий рендер армии статистов — используется и вербовкой, и тренировкой (обе
    показывают одну и ту же сводку). Принимает примитивы, не объект сервиса
    (`services.extra.ArmyStats`) — тексты не должны знать о типах сервисного слоя,
    только форматировать то, что им передали (см. CLAUDE.md, слоение проекта).
    Статисты хранятся стопками (см. `db/models/extra.py`) — `total_quantity` реалистично
    может быть сотнями миллионов/миллиардов, отсюда `format_number` без исключений."""
    if not by_rank and not cards_quantity:
        return NO_EXTRAS
    lines = "\n".join(f"  {rank}: {format_number(quantity)}" for rank, quantity in by_rank) or "  —"
    # `total_quantity` — все бойцы армии: статисты + копии уников вне отряда.
    cards_line = f" (из них уников: {format_number(cards_quantity)})" if cards_quantity else ""
    return (
        f"Всего бойцов: {format_number(total_quantity)}{cards_line}\n"
        f"⚔️ В атаке: {format_number(attack_quantity)} · 🛡 В защите: {format_number(defense_quantity)}\n"
        f"Общая мощь армии: {format_number(total_power)}\n\n"
        f"По рангам:\n{lines}"
    )
