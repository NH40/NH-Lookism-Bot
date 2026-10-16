from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Единая точка конфигурации бота. Читается из переменных окружения / .env.

    Структура и инженерные конвенции 2.0.0 сознательно зеркалят Universe Anime Planet
    (второй бот на том же сервере) — см. CLAUDE.md.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")

    database_url: str
    redis_url: str

    yookassa_provider_token: str = ""
    # Адрес БД LBP 1.3 — один раз перенести донат игроков (`services/donate.import_lbp1`).
    lbp1_database_url: str = ""

    # Пусто -> кнопка "Профиль (веб)" не показывается (см. utils/mini_app.py). Заполняется
    # только когда домен реально поднят и обслуживается общим Caddy UAP (см. CLAUDE.md,
    # "Mini App: постоянный домен").
    mini_app_url: str = ""

    log_level: str = "INFO"
    tz: str = "Europe/Moscow"

    # Оба бота (LookismBattlePlanet и Universe Anime Planet) делят один физический сервер —
    # пул соединений Postgres/лимиты держим маленькими с той же дисциплиной, что у соседа
    # (см. CLAUDE.md, "Железо и нагрузка").
    db_pool_size: int = 5
    db_max_overflow: int = 5

    throttle_interval_ms: int = 400

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.admin_ids_raw.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
