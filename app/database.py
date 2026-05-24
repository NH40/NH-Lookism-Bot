from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
 
engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
 
 
class Base(DeclarativeBase):
    pass
 
 
async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session
 
 
async def init_db():
    from app.models import user, city, building, character, squad_member, title, potion, skill, referral, auction, game_version, market, king_bot, daily_quest, clan, card_deck, circular_donat  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
