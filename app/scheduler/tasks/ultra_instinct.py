import logging
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionFactory
from app.models.user import User
from app.services.deck_service import deck_service
from app.services.squad_service import squad_service

logger = logging.getLogger(__name__)


async def ultra_instinct_tick():
    async with AsyncSessionFactory() as session:
        user_ids = list((await session.execute(
            select(User.id).where(
                or_(
                    User.ultra_instinct == True,
                    User.ui_is_donat == True,
                    User.med_genius_donat == True,
                    User.mg_level_power > 0,
                    User.mg_level_training > 0,
                    User.mg_level_income > 0,
                    User.mg_level_luck > 0,
                    User.mg_level_influence > 0,
                    User.mg_level_raid_drop > 0,
                )
            )
        )).scalars())

    for user_id in user_ids:
        try:
            async with AsyncSessionFactory() as session:
                async with session.begin():
                    user = await session.get(User, user_id)
                    if not user:
                        continue
                    if user.ui_auto_ticket:
                        await deck_service.try_get_ticket(session, user)
                    if user.ui_auto_pull and user.tickets > 0:
                        await deck_service.pull_all(session, user)
                    if user.ui_auto_recruit:
                        await _ui_recruit(session, user)
                    if user.ui_auto_train:
                        await squad_service.train(session, user)
                    # Гений медицины: авто-зелья
                    await _med_genius_auto_potion(session, user)
        except Exception as e:
            logger.error(f"ui_tick error for user {user_id}: {e}")


async def _ui_recruit(session: AsyncSession, user):
    from app.services.cooldown_service import cooldown_service
    cd_key = cooldown_service.recruit_key(user.id)
    if await cooldown_service.is_on_cooldown(cd_key):
        return
    await squad_service.recruit(session, user)


async def _med_genius_auto_potion(session: AsyncSession, user):
    """
    Гений медицины: авто-покупка зелий всех типов.
    Уровень каждого зелья (mg_level_*) определяет тир.
    Если нет активного зелья данного типа и хватает монет — покупает тир по уровню.
    """
    from app.handlers.skills.med_genius import MG_POTIONS
    from app.services.potion_service import potion_service
    from app.data.shop import MG_TIERS

    donat = getattr(user, "med_genius_donat", False)

    active    = await potion_service.get_active(session, user.id)
    active_set = {p.potion_type for p in active}

    for potion_cfg in MG_POTIONS:
        ptype       = potion_cfg["type"]
        level_field  = potion_cfg["level_field"]
        toggle_field = potion_cfg["toggle_field"]

        mg_lvl = 6 if donat else getattr(user, level_field, 0)
        if mg_lvl == 0:
            continue
        if not getattr(user, toggle_field, True):
            continue
        if ptype in active_set:
            continue

        tier = MG_TIERS[ptype][mg_lvl - 1]
        if user.nh_coins < tier.price:
            continue

        user.nh_coins -= tier.price
        user.coins_spent += tier.price
        await potion_service.apply_potion(
            session, user.id, ptype, tier.effect_value, tier.duration_minutes
        )
        active_set.add(ptype)  # не покупаем дважды в одном тике
