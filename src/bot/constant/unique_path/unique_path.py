"""Пути (константы). Дизайн — `docs/design/development_systems.md`, «Путь»."""
from __future__ import annotations

PATH_OVERCOME = "overcome"  # Преодоление
PATH_DESPAIR = "despair"  # Отчаяние
PATH_REFLECTION = "reflection"  # Отражение
PATH_ABSORPTION = "absorption"  # Поглощение
PATH_COPY = "copy"  # Копирование
PATH_INFINITE = "infinite"  # Бесконечная техника
PATH_FORESIGHT = "foresight"  # Предвидение
PATH_SENSORY = "sensory"  # Сенсорика
PATH_SURE_HIT = "sure_hit"  # Гарантированный удар
PATH_ADAPTATION = "adaptation"  # Адаптация
PATH_TRAINING = "training"  # Путь тренировок (КПД всех тренировок)
PATH_EVASION = "evasion"  # Уклонение
PATH_BUSINESS = "business"  # Бизнесмена
PATHS: tuple[str, ...] = (
    PATH_OVERCOME, PATH_DESPAIR, PATH_REFLECTION, PATH_ABSORPTION, PATH_COPY, PATH_INFINITE,
    PATH_FORESIGHT, PATH_SENSORY, PATH_SURE_HIT, PATH_ADAPTATION, PATH_TRAINING, PATH_EVASION,
    PATH_BUSINESS,
)
# Пути, которые сами копируют чужие, — в памяти противников не копируются (без рекурсии).
COPYING_PATHS: frozenset[str] = frozenset({PATH_COPY, PATH_INFINITE})

# Стадии пути (`users.path_stage`).
PATH_STAGE_NONE = 0
PATH_STAGE_CALLED = 1  # пришло «подтверждение убеждений» — квест убеждения
PATH_STAGE_CONVICTION = 2  # убеждение есть — копит фрагменты, чтобы «Пробудить путь»
PATH_STAGE_OWNED = 3  # путь выпал

CB_PATH_OPEN = "path:open"
CB_PATH_CLAIM_CONVICTION = "path:conviction"
CB_PATH_CLAIM_PATH = "path:claim"  # «🎲 Пробудить путь» за фрагменты
CB_PATH_LEVEL_UP = "path:up"
CB_PATH_ACTIVATE_PREFIX = "path:act:"

# Источник очков пути «ежедневный заход» (остальные источники — события `TASK_*` из
# `constant/dev_quest`, тот же `emit()`).
PATH_SOURCE_DAILY = "daily"

CB_PATH_AWAKEN_PREFIX = "path:awaken:"  # + "random" | код купленного пути
PATH_AWAKEN_RANDOM = "random"
CB_PATH_LEVEL_UP2 = "path:up2"
CB_PATH_ACTIVATE2_PREFIX = "path:act2:"
