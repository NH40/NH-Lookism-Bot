import logging
from datetime import datetime, timezone

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionFactory
from app.models.user import User
from app.models.potion import ActivePotion
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
                    User.fame_gana_ui_control == True,
                )
            )
        )).scalars())

    if not user_ids:
        return

    # Одна сессия на всех пользователей; savepoint изолирует ошибки.
    async with AsyncSessionFactory() as session:
        async with session.begin():
            # Батч-загрузка всех UI-юзеров одним запросом (вместо N session.get)
            users_result = await session.execute(
                select(User).where(User.id.in_(user_ids))
            )
            users_map = {u.id: u for u in users_result.scalars().all()}

            # Батч-загрузка активных зелий для всех юзеров одним запросом
            now = datetime.now(timezone.utc)
            potions_result = await session.execute(
                select(ActivePotion).where(
                    ActivePotion.user_id.in_(user_ids),
                    ActivePotion.expires_at > now,
                )
            )
            potions_by_user: dict[int, list[ActivePotion]] = {}
            for p in potions_result.scalars().all():
                potions_by_user.setdefault(p.user_id, []).append(p)

            for user_id in user_ids:
                try:
                    async with session.begin_nested():
                        user = users_map.get(user_id)
                        if not user:
                            continue
                        if user.ui_auto_ticket:
                            await deck_service.try_get_ticket(session, user)
                        if user.ui_auto_pull and user.tickets > 0:
                            await deck_service.pull_all(session, user)
                        # Слава — Гана «Контроль ультра инстинкта»: авто-вербовка/тренировка
                        # без покупки УИ II, пока фрагмент удержан
                        if user.ui_auto_recruit or user.fame_gana_ui_control:
                            await _ui_recruit(session, user)
                            if user.fame_set_gana:
                                # Бафф сета «Истинный ультра инстинкт»: х2 за тик
                                await _ui_recruit(session, user, bypass_cd=True)
                        if user.ui_auto_train or user.fame_gana_ui_control:
                            await squad_service.train(session, user)
                            if user.fame_set_gana:
                                await squad_service.train(session, user, bypass_cd=True)
                        # Гений медицины: авто-зелья (используем предзагруженные зелья)
                        await _med_genius_auto_potion(
                            session, user, potions_by_user.get(user_id, [])
                        )
                except Exception as e:
                    logger.error(f"ui_tick error for user {user_id}: {e}")


async def _ui_recruit(session: AsyncSession, user, bypass_cd: bool = False):
    from app.services.cooldown_service import cooldown_service
    cd_key = cooldown_service.recruit_key(user.id)
    if not bypass_cd and await cooldown_service.is_on_cooldown(cd_key):
        return
    await squad_service.recruit(session, user, bypass_cd=bypass_cd)


async def _med_genius_auto_potion(
    session: AsyncSession, user, preloaded_potions: list | None = None
):
    """
    Гений медицины: авто-покупка зелий всех типов.
    Уровень каждого зелья (mg_level_*) определяет тир.
    Если нет активного зелья данного типа и хватает монет — покупает тир по уровню.
    preloaded_potions — уже загруженные активные зелья (опционально, для батч-режима).
    """
    from app.handlers.skills.med_genius import MG_POTIONS
    from app.services.potion_service import potion_service
    from app.data.shop import MG_TIERS

    donat = getattr(user, "med_genius_donat", False)

    if preloaded_potions is not None:
        active = preloaded_potions
    else:
        active = await potion_service.get_active(session, user.id)
    active_set = {p.potion_type for p in active}

    for potion_cfg in MG_POTIONS:
        ptype        = potion_cfg["type"]
        level_field  = potion_cfg["level_field"]
        toggle_field = potion_cfg["toggle_field"]
        pref_field   = potion_cfg.get("pref_field", "")

        mg_lvl = 6 if donat else getattr(user, level_field, 0)
        if mg_lvl == 0:
            continue
        if not getattr(user, toggle_field, True):
            continue
        if ptype in active_set:
            continue

        # Предпочитаемый уровень авто-покупки (если задан и не превышает доступный)
        pref_lvl = getattr(user, pref_field, 0) if pref_field else 0
        if pref_lvl and pref_lvl <= mg_lvl:
            mg_lvl = pref_lvl

        tier = MG_TIERS[ptype][mg_lvl - 1]
        if user.nh_coins < tier.price:
            continue

        user.nh_coins -= tier.price
        user.coins_spent += tier.price
        await potion_service.apply_potion(
            session, user.id, ptype, tier.effect_value, tier.duration_minutes
        )
        active_set.add(ptype)  # не покупаем дважды в одном тике
