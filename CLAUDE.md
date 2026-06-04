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

**Layered pattern:** Handlers → Services → Repositories → SQLAlchemy ORM → PostgreSQL. Redis stores FSM state and all cooldowns.

**Request lifecycle:** Each Telegram update passes through 4 middlewares in order:

1. `DbSessionMiddleware` — creates an async SQLAlchemy session, injects `session` into handler data
2. `UserLoaderMiddleware` — loads or creates the `User` row from `tg_id`, injects `user` into handler data; blocks banned users
3. `NetworkErrorMiddleware` — handles Telegram API transient errors
4. `RateLimitMiddleware` — limits callbacks to 0.5 req/sec per user via Redis

**All handlers receive `(cb/message, session: AsyncSession, user: User)` injected by the middleware stack.**

**Background scheduler (APScheduler)** — tasks live in `app/scheduler/tasks/` (one file per domain), registered in `app/scheduler/setup.py`, intervals in `app/config/scheduler_config.py`:

| Task                  | Interval  | Purpose                                               |
| --------------------- | --------- | ----------------------------------------------------- |
| `income_tick`         | 1 min     | Distribute building income to all users               |
| `ultra_instinct_tick` | 1 min     | Auto-actions (recruit/train/ticket) for UI users      |
| `auction_round_tick`  | 10 sec    | Advance auction timers and resolve round winners      |
| `auction_start_tick`  | 2 min     | Start new auctions                                    |
| `clan_war_tick`       | 5 min     | Finish expired clan wars, distribute treasury rewards |
| `clan_auction_tick`   | 1 min     | Finish expired clan auctions                          |
| `region_war_tick`     | 5 min     | Finish expired Korean region wars, transfer ownership |
| `campaign_tick`       | 2 min     | Complete expired campaigns                            |
| `boss_tick`           | 60 sec    | Spawn/expire raid bosses                              |
| `referral_power_tick` | 30 min    | Recalculate teacher referral power bonuses            |
| `daily_tick`          | 00:00 UTC | Daily bonuses (circ_daily_districts)                  |
| `bank_credit_tick`    | 1 min     | Bank loan interest                                    |
| `storage_fee_tick`    | 1 min     | Bank storage fees                                     |
| `investment_tick`     | 1 min     | Bank investment maturity                              |
| `war_genius_tick`     | 1 min     | Auto-attack raids (War Genius skill)                  |

Scheduler tasks get the bot reference via `app/bot_instance.get_bot()`.

## Key Files

| File                               | Purpose                                                                                                               |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `app/main.py`                      | Entry point: DB init, city/region init, router registration, scheduler start, polling                                 |
| `app/models/user.py`               | Central User model (160+ columns — stats, bonuses, phase progress, all denormalized for performance)                  |
| `app/config/game_balance.py`       | **All numeric balance constants** (costs, multipliers, war durations, thresholds) — change here, not in service logic |
| `app/config/scheduler_config.py`   | Scheduler intervals                                                                                                   |
| `app/database.py`                  | Async SQLAlchemy engine, `AsyncSessionFactory`, `Base`                                                                |
| `app/services/cooldown_service.py` | Redis-backed cooldown helpers used by every combat/training handler                                                   |
| `app/utils/safe_edit.py`           | `safe_edit()` — wraps `message.edit_text()` silencing MessageNotModified errors; use instead of raw `edit_text`       |
| `app/utils/formatters.py`          | `fmt_num()`, `fmt_ttl()` — shared number/time formatters                                                              |

## Game Phases

**Gang → King → Fist → Emperor (prestige resets)**

- **Gang**: attack cities to capture districts; need 10+ cities to advance
- **King**: fight King Bots for influence; need 10 bot wins to advance
- **Fist**: defeat 10 Fist Bots; advance to Emperor
- **Emperor**: prestige — full reset, earn permanent bonuses per prestige level

`attack.py` dispatches to the correct phase handler via `build_attack_menu()`. Each phase has its own handler (`app/handlers/game/`) and service (`app/services/game/`). The game service inherits three mixins: `_queries_mixin`, `_promotions_mixin`, `_districts_mixin`.

## Clan System

`ClanService` is a composite of 10 service mixins (base/invite/war/exchange/shop/auction/treasury/upgrades/donat/region) merged in `app/services/clan/__init__.py`.

**Clan member ranks:** `owner` / `deputy` / `captain` / `member` — stored in `ClanMember.rank`. Deputies and owners can start wars and auctions; only owners can change ranks.

**Region wars** (`app/services/clan/region.py`): Clans with ≤15 members compete for one of 16 Korean regions over 6 hours. Score = sum of per-player activity flags (train/attack_gang/attack_king/attack_fist/spend — max 5 per player). Minimum 10 points needed to capture. Call `clan_service.record_activity(session, user_id, clan_id, action)` from any handler where activity should count.

## Cooldown Pattern

All combat and training cooldowns go through Redis via `cooldown_service`. The canonical pattern:

```python
from app.services.cooldown_service import cooldown_service

cd_key = f"some_action:{user.id}"
if await cooldown_service.is_on_cooldown(cd_key):
    ttl = await cooldown_service.get_ttl(cd_key)
    # show cooldown message
    return
# ... do action ...
await cooldown_service.set_cooldown(cd_key, SECONDS)
```

**Race condition fix:** Attack handlers (boss/emperor/gang/king/fist) must acquire a Redis lock BEFORE checking cooldown to prevent double-execution on concurrent taps. See `app/services/game/_queries_mixin.py` for the locking pattern.

## Notifications from Scheduler Tasks

Scheduler tasks run in a separate async context — they open their own sessions via `AsyncSessionFactory`. The two-phase pattern (commit first, notify second) prevents holding a transaction open during slow Telegram sends:

```python
async with AsyncSessionFactory() as session:
    async with session.begin():
        # mutate state, collect notification data into a list
        pass  # committed here

# now send notifications outside the transaction
bot = get_bot()
await _send_notifications(bot, tg_ids, text)
```

## Database & Migrations

Tables are created on startup via `metadata.create_all()` in `app/database.py`. New schema changes are applied **manually** via `migration.sql` — there is no Alembic migration history; Alembic is present but unused for versioned migrations.

`app/main.py` runs `init_cities()` and `init_regions()` on every startup (idempotent — skips if data already exists).

## Configuration

All settings come from `.env` (see `.env.example`):

- `BOT_TOKEN`, `ADMIN_IDS`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
- `DEBUG` (default: false)

Docker Compose maps PostgreSQL to host port 5433. Config is loaded via pydantic-settings in `app/config/settings.py`; all other modules import from `app/config` (the package re-exports everything).

## Adding New Features — Checklist

1. **Model** in `app/models/` → export from `app/models/__init__.py`
2. **Service** in `app/services/` (or as a mixin added to a composite service)
3. **Handler** in `app/handlers/` → include router in the module's `__init__.py` and in `app/main.py`
4. **Scheduler task** (if needed): add function to `app/scheduler/tasks/clan.py` (or a new file), export from `app/scheduler/tasks/__init__.py`, register in `app/scheduler/setup.py`, add interval constant to `app/config/scheduler_config.py`
5. **Balance constants** in `app/config/game_balance.py`
6. **Migration** in `migration.sql`

## No Tests or Linter Config

There is no pytest, unittest, or linting configuration. All verification is manual via Docker logs.

docker-compose up --build -d
git pull
