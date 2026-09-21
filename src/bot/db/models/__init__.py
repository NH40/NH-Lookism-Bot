"""Импортировать все модели здесь, чтобы Base.metadata видел их (нужно для Alembic
autogenerate) — та же плоская структура db/models, что в Universe Anime Planet: каждая
модель уже сама по себе один домен, без соседних файлов (см. CLAUDE.md UAP).

Наполняется по мере переноса доменов из LookismBattlePlanet 1.0. Порядок импорта здесь
не влияет на порядок создания таблиц (Alembic/`Base.metadata.create_all` сортируют по
FK-зависимостям сами), но `Country`/`City` идут раньше `User` для читаемости — на них
ссылается `User.country_code`/`city_id`.
"""

from bot.db.models.country import Country  # noqa: F401
from bot.db.models.city import City  # noqa: F401
from bot.db.models.user import User  # noqa: F401
from bot.db.models.gang import Gang  # noqa: F401
from bot.db.models.extra import Extra  # noqa: F401
