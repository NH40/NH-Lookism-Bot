#!/usr/bin/env sh
# Тот же удобный паттерн, что в NH-BTFChat: `docker compose up -d --build` — единственная
# команда, которая нужна для деплоя. Миграции применяются автоматически при старте
# контейнера бота, руками `alembic upgrade head` гонять не нужно.
#
# Отличие от BTFChat: этот образ используется ДВУМЯ сервисами (bot и manager, см.
# docker-compose.yml) с разными командами запуска — если аргументы переданы (manager
# запускается через `command: python manager.py`), выполняем их как есть, без миграций
# (незачем гонять alembic из сервиса, который не трогает схему). Без аргументов (обычный
# запуск bot) — сперва миграции, потом сам бот.
set -e

if [ "$#" -eq 0 ]; then
    python -m alembic upgrade head
    exec python -m bot.main
else
    exec "$@"
fi
