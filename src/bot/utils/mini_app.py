"""Сборка ссылок на Mini App (`MINI_APP_URL`) — портировано из Universe Anime Planet
почти дословно (см. CLAUDE.md UAP, "Долгая загрузка картинок..." — там же объяснение,
зачем нужен `?v=`), включая тот же найденный там баг с web_app-кнопками вне личных
чатов.
"""
from __future__ import annotations

from aiogram.enums import ChatType

# Версия статики Mini App — бампить вручную при каждом деплое фронтенда (см. UAP:
# Telegram кэширует Mini App URL агрессивнее, чем управляется серверными заголовками
# Cache-Control — один и тот же URL после редеплоя может продолжать открывать СТАРЫЙ
# index.html/JS, закэшированный клиентом раньше, чем на Caddy появился `no-cache`).
# Приклеенный `?v=N` делает URL кнопки формально НОВЫМ при каждом бампе.
MINI_APP_ASSET_VERSION = 1


def mini_app_url(base_url: str, *, view: str | None = None) -> str:
    params = [f"v={MINI_APP_ASSET_VERSION}"]
    if view:
        params.append(f"view={view}")
    return f"{base_url}?{'&'.join(params)}"


def resolve_mini_app_base_url(raw_url: str | None, chat_type: str) -> str | None:
    """Telegram разрешает `web_app`-кнопки ТОЛЬКО в приватных чатах — вне личных чатов
    Bot API целиком отклоняет `sendMessage` с такой кнопкой (400 Bad Request), а не
    просто не показывает её (наступили на это в UAP 2026-08-15) — если не отфильтровать
    здесь, экран с "(веб)"-кнопкой не отправился бы вообще, ни текст, ни остальные
    кнопки, стоило открыть его в группе."""
    if not raw_url or chat_type != ChatType.PRIVATE:
        return None
    return raw_url
