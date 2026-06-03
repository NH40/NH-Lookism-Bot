# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

**With Docker Compose (recommended):**

```bash
docker-compose up -d --build
docker-compose logs bot --tail=20
```

**Locally:**

```bash
pip install -r requirements.txt
python -m app.main
```

**Manager utility (backups, DB init):**

```bash
python manager.py backup          # Create SQL dump
python manager.py restore <file>  # Restore from backup
python manager.py migrate         # Initialize database tables
python manager.py stats           # Show player statistics
```

## Architecture

**Layered pattern:** Handlers → Services → Repositories → SQLAlchemy ORM → PostgreSQL. Redis stores FSM state and cooldowns.

**Request lifecycle:** Each Telegram update passes through 4 middlewares in order:

1. `DbSessionMiddleware` — creates an async SQLAlchemy session
2. `UserLoaderMiddleware` — loads or creates the `User` row from `tg_id`
3. `NetworkErrorMiddleware` — handles Telegram API errors
4. `RateLimitMiddleware` — limits callbacks to 0.5 req/sec per user

**Background scheduler (APScheduler):**

- `income_tick` every 1 min — distributes building income to all users
- `ultra_instinct_tick` every 1 min — auto-actions for users with Ultra Instinct enabled
- `auction_round_tick` every 30 sec — advances auction timers and resolves round winners
- `auction_start_tick` every 15 min — starts new auctions and notifies players
- `clan_war_tick` every 5 min — finishes clan wars and distributes rewards

Scheduler tasks obtain a bot reference via the singleton in [app/bot_instance.py](app/bot_instance.py).

## Key Files

| File                                             | Purpose                                                                   |
| ------------------------------------------------ | ------------------------------------------------------------------------- |
| [app/main.py](app/main.py)                       | Entry point: DB init, router registration, scheduler start, polling       |
| [app/models/user.py](app/models/user.py)         | Central User model (110+ columns covering stats, bonuses, phase progress) |
| [app/config.py](app/config.py)                   | pydantic-settings config loaded from `.env`                               |
| [app/database.py](app/database.py)               | Async SQLAlchemy engine and session factory                               |
| [app/scheduler/tasks.py](app/scheduler/tasks.py) | All background job implementations                                        |

**Game phase logic lives in** [app/services/game/](app/services/game/) — `gang.py`, `king.py`, `fist.py` — and is dispatched by [app/services/game_service.py](app/services/game_service.py).

**Combat calculations** are in [app/services/combat_service.py](app/services/combat_service.py).

**Balancing constants** (costs, multipliers, boss specs, tier configs) live in [app/constants/](app/constants/) and static data definitions (cities, characters, buildings) in [app/data/](app/data/).

## Game Phases

Gang → King (capture 10+ districts) → Fist (defeat 10 bots) → Emperor (prestige resets).

Each phase has its own handler ([app/handlers/game/](app/handlers/game/)) and service ([app/services/game/](app/services/game/)).

## Database & Migrations

Tables are created on startup via `metadata.create_all()` in [app/database.py](app/database.py). New schema changes are applied manually via [migration.sql](migration.sql) — there is no Alembic migration history; Alembic is present but unused for versioned migrations.

## Configuration

All settings come from `.env` (see [.env.example](.env.example)):

- `BOT_TOKEN`, `ADMIN_IDS`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
- `DEBUG` (default: false)

Docker Compose maps PostgreSQL to host port 5433.

## No Tests or Linter Config

There is no pytest, unittest, or linting configuration in this repository. All verification is manual or via Docker logs.

docker-compose up --build -d
git pull
