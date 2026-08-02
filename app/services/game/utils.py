from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.formatters import fmt_num

# Слабейшие статисты гибнут первыми (реверс squad_service.py rank_order).
_STATIST_RANK_WEAKEST_FIRST = [
    "F", "E", "D", "C", "B", "A", "S", "SS", "SSS", "SR", "SSR",
    "UR", "LR", "MP", "X", "XX", "XXX", "DX", "ERROR",
]

# Слабейшие карточки гибнут первыми (реверс clan/exchange.py RANK_ORDER,
# см. app/data/characters.py CharacterRankConfig — member слабее perfection).
_CARD_RANK_WEAKEST_FIRST = [
    "member", "boss", "king", "strong_king", "gen_zero",
    "new_legend", "legend", "peak", "absolute", "perfection",
]


_STAR_MULT = {1: 1.10, 2: 1.20, 3: 1.30, 4: 1.40, 5: 1.50}


def _star_mult(stars: int) -> float:
    return _STAR_MULT.get(stars, 1.0)


async def apply_battle_casualties(
    session: AsyncSession, attacker: User, defender: User, attacker_won: bool
) -> dict:
    """Потери статистов и карточек в PvP-бою (патч 1.3.1: король/трон/император
    больше не уничтожает проигравшего целиком — оба участника платят цену).

    Потери считаются ПО ВКЛАДУ В МОЩЬ, а не по количеству юнитов — иначе
    атакующий с малым числом мощных бойцов гарантированно теряет 100% своего
    состава против защитника с большой толпой слабых статистов, даже если
    реальная боевая мощь атакующего в разы больше (баг патча 1.3.1, отчёт
    владельца от 02.08.2026: "170 млрд мощи → 0" против втрое более слабой
    цели). Слабейшие юниты (по рангу, затем по мощи) гибнут первыми.

    Правила зависят от РОЛИ, не суммируются друг с другом:
      - Атакующий ВСЕГДА теряет долю СВОЕГО состава, равную
        min(мощь_защитника / мощь_атакующего, 100%) — то есть его итоговая
        боевая мощь падает ровно на мощь защитника, но не ниже нуля.
        Действует независимо от исхода боя.
      - Защитник, если он ПРОИГРАЛ, ДОПОЛНИТЕЛЬНО теряет
        PVP_LOSER_CASUALTY_PERCENT% СВОЕЙ ЖЕ мощи (не количества юнитов).
        Победивший защитник по этой функции не теряет ничего.

    Победитель/трофеи (районы, города, монеты) эта функция не трогает —
    только живая сила."""
    from sqlalchemy import select, delete as sql_delete
    from app.models.squad_member import SquadMember
    from app.models.character import UserCharacter
    from app.models.card_deck import UserDeck
    from app.repositories.squad_repo import squad_repo
    from app.config.game_balance import PVP_LOSER_CASUALTY_PERCENT

    async def _statist_rows(uid: int):
        rows = (await session.execute(
            select(SquadMember).where(SquadMember.user_id == uid)
        )).scalars().all()
        total_power = sum(r.base_power * _star_mult(r.stars) * r.count for r in rows)
        return rows, total_power

    async def _kill_statists_by_power(rows: list, power_budget: float) -> int:
        if power_budget <= 0:
            return 0
        by_rank: dict[str, list] = {}
        for r in rows:
            by_rank.setdefault(r.rank, []).append(r)
        for pool in by_rank.values():
            pool.sort(key=lambda r: r.base_power * _star_mult(r.stars))
        killed = 0
        remaining = power_budget
        for rank in _STATIST_RANK_WEAKEST_FIRST:
            if remaining <= 0:
                break
            for r in by_rank.get(rank, []):
                if remaining <= 0:
                    break
                unit_power = r.base_power * _star_mult(r.stars)
                if unit_power <= 0:
                    continue
                row_power = unit_power * r.count
                if row_power <= remaining:
                    take = r.count
                else:
                    take = min(r.count, int(remaining // unit_power))
                    if take <= 0:
                        take = 1  # добираем хотя бы 1 юнит, чтобы не зависнуть на дробном остатке
                r.count -= take
                killed += take
                remaining -= take * unit_power
                if r.count <= 0:
                    await session.delete(r)
        return killed

    async def _card_rows(uid: int) -> list[tuple[int, str, int]]:
        return list((await session.execute(
            select(UserCharacter.id, UserCharacter.rank, UserCharacter.power).where(
                UserCharacter.user_id == uid
            )
        )).all())

    async def _kill_cards_by_power(rows: list[tuple[int, str, int]], power_budget: float) -> int:
        if power_budget <= 0 or not rows:
            return 0
        by_rank: dict[str, list[tuple[int, int]]] = {}
        for cid, rank, power in rows:
            by_rank.setdefault(rank, []).append((cid, power))
        chosen: list[int] = []
        remaining = power_budget
        for rank in _CARD_RANK_WEAKEST_FIRST:
            if remaining <= 0:
                break
            pool = sorted(by_rank.pop(rank, []), key=lambda x: x[1])
            for cid, power in pool:
                if remaining <= 0:
                    break
                chosen.append(cid)
                remaining -= power
        if remaining > 0 and by_rank:
            # Ранг вне списка (новый/неизвестный) — добираем что осталось.
            leftover = sorted(
                (cp for pool in by_rank.values() for cp in pool), key=lambda x: x[1]
            )
            for cid, power in leftover:
                if remaining <= 0:
                    break
                chosen.append(cid)
                remaining -= power
        if not chosen:
            return 0
        await session.execute(sql_delete(UserDeck).where(UserDeck.char_id.in_(chosen)))
        await session.execute(sql_delete(UserCharacter).where(UserCharacter.id.in_(chosen)))
        return len(chosen)

    atk_rows, atk_squad_power = await _statist_rows(attacker.id)
    def_rows, def_squad_power = await _statist_rows(defender.id)
    atk_cards = await _card_rows(attacker.id)
    def_cards = await _card_rows(defender.id)
    atk_card_power = sum(p for _, _, p in atk_cards)
    def_card_power = sum(p for _, _, p in def_cards)

    # Атакующий: его итоговая мощь падает ровно на мощь защитника (не ниже
    # нуля) — реализуем как единую долю мощи, снятую равномерно с обеих
    # категорий его состава, независимо от исхода боя.
    #
    # Доля считается по ФИНАЛЬНОЙ combat_power (attacker.combat_power /
    # defender.combat_power), а НЕ по сырым суммам atk_total_power/
    # def_total_power — combat_power включает престиж/донат-титул/
    # мастерство/клан-земли множители поверх сырой суммы статистов+карт,
    # и эти множители у разных игроков разные. Доля по сырым суммам могла
    # схлопнуться к 100% даже когда финальная мощь атакующего в разы
    # больше защитника (репро: "на королях всю мощь потеряли", 02.08.2026,
    # после первого прохода фикса бага 17).
    atk_fraction = (
        min(defender.combat_power / attacker.combat_power, 1.0)
        if attacker.combat_power > 0 else 0.0
    )
    atk_statists_lost = await _kill_statists_by_power(atk_rows, atk_squad_power * atk_fraction)
    atk_cards_lost = await _kill_cards_by_power(atk_cards, atk_card_power * atk_fraction)

    # Защитник: доп. PVP_LOSER_CASUALTY_PERCENT% своей же мощи, только если проиграл.
    def_statists_lost = 0
    def_cards_lost = 0
    if attacker_won:
        def_fraction = PVP_LOSER_CASUALTY_PERCENT / 100
        def_statists_lost = await _kill_statists_by_power(def_rows, def_squad_power * def_fraction)
        def_cards_lost = await _kill_cards_by_power(def_cards, def_card_power * def_fraction)

    await session.flush()
    await squad_repo.update_user_combat_power(session, attacker)
    await squad_repo.update_user_combat_power(session, defender)

    return {
        "attacker_statists_lost": atk_statists_lost, "defender_statists_lost": def_statists_lost,
        "attacker_cards_lost": atk_cards_lost, "defender_cards_lost": def_cards_lost,
    }


async def notify_pvp_attack(
    attacker: User, defender: User,
    win: bool, phase: str,
    attacker_power: int | None = None, defender_power: int | None = None,
) -> None:
    """attacker_power/defender_power — сила НА МОМЕНТ БОЯ (result["attacker_power"]/
    ["defender_power"] из fight_player). Передавать явно там, где после боя
    вызывается apply_battle_casualties — она мутирует combat_power ДО этого
    уведомления, поэтому чтение .combat_power здесь показывало бы игроку
    уже урезанную посмертную мощь атакующего вместо той, что реально решила
    бой (баг: "Его мощь: 0" у реального победившего игрока)."""
    try:
        if not defender.notifications_enabled or not getattr(defender, "notif_pvp", True):
            return
        from app.bot_instance import get_bot
        bot = get_bot()
        if not bot:
            return
        atk_power = attacker.combat_power if attacker_power is None else attacker_power
        def_power = defender.combat_power if defender_power is None else defender_power
        phase_names = {
            "gang": "банды", "king": "королей",
            "king_challenge": "за трон", "emperor_pvp": "императоров",
        }
        phase_str = phase_names.get(phase, "")
        if win:
            text = (
                f"⚔️ <b>На вас напали!</b>\n\n"
                f"<b>{attacker.full_name}</b> атаковал вас "
                f"в PvP {phase_str} и победил!\n\n"
                f"💪 Его мощь: {fmt_num(atk_power)}\n"
                f"⚔️ Ваша мощь: {fmt_num(def_power)}"
            )
        else:
            text = (
                f"🛡 <b>Атака отражена!</b>\n\n"
                f"<b>{attacker.full_name}</b> атаковал вас "
                f"в PvP {phase_str} и проиграл!\n\n"
                f"💪 Его мощь: {fmt_num(atk_power)}\n"
                f"⚔️ Ваша мощь: {fmt_num(def_power)}"
            )
        await bot.send_message(defender.tg_id, text, parse_mode="HTML")
    except Exception:
        pass


async def notify_country_city_loss(
    session: AsyncSession, country: str, defender: User,
    attacker: User, city_names: list[str],
) -> None:
    """Рассылка всем игрокам проигравшей страны — их император уступил
    города в PvP Императоров. Не шлёт самому defender — он уже получает
    личное DM через notify_pvp_attack."""
    if not city_names:
        return
    try:
        from app.bot_instance import get_bot
        from sqlalchemy import select
        bot = get_bot()
        if not bot:
            return

        cities_str = ", ".join(city_names)
        text = (
            f"🏛 <b>Ваша страна потеряла территорию!</b>\n\n"
            f"Император <b>{defender.full_name}</b> проиграл в PvP Императоров "
            f"императору <b>{attacker.full_name}</b> и уступил {len(city_names)} "
            f"{'город' if len(city_names) == 1 else 'города/городов'}: {cities_str}.\n\n"
            f"Короли и банды в этих городах теперь платят городской налог "
            f"новому владельцу."
        )
        rows = (await session.execute(
            select(User.tg_id, User.notifications_enabled).where(
                User.country == country,
                User.id != defender.id,
            )
        )).all()
        for tg_id, notif_enabled in rows:
            if not notif_enabled:
                continue
            try:
                await bot.send_message(tg_id, text, parse_mode="HTML")
            except Exception:
                pass
    except Exception:
        pass