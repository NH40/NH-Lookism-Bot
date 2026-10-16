"""FastAPI-приложение Mini App — read-write почти целиком (см. api/db.py).

Роутеры подключены только для доменов, у которых реально есть свой экран в Mini App
(7 вкладок нижней навигации + их подэкраны, см. `docs/design/
lookism_battle_planet_2_raw_notes.md`) — start/common/admin/help/referral/promo/
donate/payment остаются ЧИСТО бот-доменами без своего API (нет Mini App эквивалента
в текущем дизайне, см. CLAUDE.md).

TODO: `api/db.py`/`api/auth.py` уже рабочие (порт из Universe Anime Planet), но
роутеры — TODO-заглушки без реальных путей, подключать по мере наполнения
конкретного домена, не все разом.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.db import engine
from api.push import close_bot
from api.routers import awakening
from api.routers import bloodline
from api.routers import boss
from api.routers import battle_pass
from api.routers import business
from api.routers import campaign
from api.routers import card
from api.routers import casino
from api.routers import exchange
from api.routers import empire
from api.routers import country
from api.routers import guide
from api.routers import intel
from api.routers import promo
from api.routers import stats
from api.routers import clan
from api.routers import donate
from api.routers import collection
from api.routers import development
from api.routers import district
from api.routers import gacha
from api.routers import gang
from api.routers import img
from api.routers import genius
from api.routers import map as map_router
from api.routers import mastery
from api.routers import top as top_router
from api.routers import profile
from api.routers import quest
from api.routers import raid
from api.routers import recruit
from api.routers import settings as settings_router
from api.routers import shop
from api.routers import teacher
from api.routers import training
from api.routers import ultra_instinct
from api.routers import unique_path
from api.routers import unique_technique


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_bot()
    await engine.dispose()


app = FastAPI(title="LookismBattlePlanet API", lifespan=lifespan)

# В проде Caddy/аналог проксирует и фронтенд, и /api под одним доменом — CORS не
# нужен вовсе. allow_methods шире, чем у read-only Mini App UAP — тут почти всё пишет.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["X-Telegram-Init-Data", "Content-Type"],
)

app.include_router(profile.router)
app.include_router(battle_pass.router)
app.include_router(img.router)
app.include_router(map_router.router)
app.include_router(district.router)
app.include_router(gang.router)
app.include_router(recruit.router)
app.include_router(business.router)
app.include_router(training.router)
app.include_router(development.router)
app.include_router(teacher.router)
app.include_router(mastery.router)
app.include_router(top_router.router)
app.include_router(card.router)
app.include_router(gacha.router)
app.include_router(collection.router)
app.include_router(raid.router)
app.include_router(campaign.router)
app.include_router(boss.router)
app.include_router(ultra_instinct.router)
app.include_router(unique_technique.router)
app.include_router(unique_path.router)
app.include_router(bloodline.router)
app.include_router(genius.router)
app.include_router(awakening.router)
app.include_router(clan.router)
app.include_router(donate.router)
app.include_router(quest.router)
app.include_router(shop.router)
app.include_router(exchange.router)
app.include_router(empire.router)
app.include_router(country.router)
app.include_router(guide.router)
app.include_router(intel.router)
app.include_router(promo.router)
app.include_router(stats.router)
app.include_router(casino.router)
app.include_router(settings_router.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
