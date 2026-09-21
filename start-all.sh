#!/usr/bin/env bash
# Единая точка запуска ОБОИХ ботов, живущих на одном сервере — LookismBattlePlanet
# (этот репозиторий) и Universe Anime Planet (сосед). Каждый уже самодостаточен своим
# собственным docker-compose.yml (свои postgres/redis, без публикации их портов наружу —
# см. CLAUDE.md, "Железо и нагрузка") — этот скрипт просто прогоняет `docker compose`
# в обеих директориях ОДНОЙ командой, тем же принципом простоты, что у NH-BTFChat
# (`docker compose up -d --build`), не сливая их в один docker-compose проект: имена
# сервисов (postgres/redis/bot) совпадают в обоих файлах, слияние через `-f` перезаписало
# бы один набор сервисов другим вместо запуска обоих.
#
# Копия этого скрипта лежит и в NH-Universe-Anime-Planet (с обратными путями) — рабочий
# со стороны ЛЮБОГО из двух репозиториев, не только этого.
#
# Использование:
#   ./start-all.sh            # git pull + docker compose up -d --build в обоих проектах
#   ./start-all.sh up         # то же самое, без git pull
#   ./start-all.sh down       # остановить оба (без удаления volumes/данных)
#   ./start-all.sh restart    # down + up
#   ./start-all.sh ps         # статус контейнеров обоих проектов
#   ./start-all.sh logs       # логи сервиса bot обоих проектов, follow
#
# Предполагает тот же layout, что на сервере — оба репозитория лежат РЯДОМ:
#   .../NH-Lookism-Bot
#   .../NH-Universe-Anime-Planet

set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LBP_DIR="$SELF_DIR"
UAP_DIR="$SELF_DIR/../NH-Universe-Anime-Planet"

if [ ! -d "$UAP_DIR" ]; then
  echo "Не найден Universe Anime Planet рядом ($UAP_DIR) — ожидается, что оба репозитория лежат соседними директориями (тот же layout, что на сервере)." >&2
  exit 1
fi

cmd="${1:-all}"

run_in() {
  local dir="$1"
  shift
  echo "==> [$dir] $*"
  (cd "$dir" && "$@")
}

case "$cmd" in
  all)
    run_in "$LBP_DIR" git pull
    run_in "$UAP_DIR" git pull
    run_in "$LBP_DIR" docker compose up -d --build
    run_in "$UAP_DIR" docker compose up -d --build
    ;;
  up)
    run_in "$LBP_DIR" docker compose up -d --build
    run_in "$UAP_DIR" docker compose up -d --build
    ;;
  down)
    run_in "$LBP_DIR" docker compose down
    run_in "$UAP_DIR" docker compose down
    ;;
  restart)
    "$0" down
    "$0" up
    ;;
  ps)
    run_in "$LBP_DIR" docker compose ps
    run_in "$UAP_DIR" docker compose ps
    ;;
  logs)
    (cd "$LBP_DIR" && docker compose logs -f --tail=50 bot) &
    (cd "$UAP_DIR" && docker compose logs -f --tail=50 bot) &
    wait
    ;;
  *)
    echo "Неизвестная команда: $cmd (ожидается: all|up|down|restart|ps|logs)" >&2
    exit 1
    ;;
esac
