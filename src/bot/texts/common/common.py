"""Общее reply-меню бота (тексты)."""
from __future__ import annotations

from bot.utils.formatting import format_number

SECTION_IN_DEVELOPMENT = "🚧 Раздел в разработке — скоро."

NO_EXTRAS = "Статистов пока нет."


def render_army_block(*, total_quantity: int, total_power: int, by_rank: list[tuple[str, int]]) -> str:
    """Общий рендер армии статистов — используется и вербовкой, и тренировкой (обе
    показывают одну и ту же сводку). Принимает примитивы, не объект сервиса
    (`services.extra.ArmyStats`) — тексты не должны знать о типах сервисного слоя,
    только форматировать то, что им передали (см. CLAUDE.md, слоение проекта).
    Статисты хранятся стопками (см. `db/models/extra.py`) — `total_quantity` реалистично
    может быть сотнями миллионов/миллиардов, отсюда `format_number` без исключений."""
    if not by_rank:
        return NO_EXTRAS
    lines = "\n".join(f"  {rank}: {format_number(quantity)}" for rank, quantity in by_rank)
    return (
        f"Всего статистов: {format_number(total_quantity)}\n"
        f"Общая мощь армии: {format_number(total_power)}\n\n"
        f"По рангам:\n{lines}"
    )
