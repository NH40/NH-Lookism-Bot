"""
Бизнес-логика системы Боссов.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete as sa_delete, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.bosses import (
    ARCHANGEL_DEBUFF_ATTACKS,
    ARCHANGEL_DONATE_LABELS,
    ARCHANGEL_DONATE_WEIGHTS,
    ARCHANGEL_HEAL_PCT,
    ARCHANGEL_SHIELD_PCT,
    BOSS_ARCHANGEL_FRAG_DIVISOR,
    BOSS_ARCHANGEL_FRAG_MAX,
    BOSS_ARCHANGEL_FRAG_MIN,
    BOSS_ATTACK_CD_MIN,
    BOSS_ATTACK_CD_SECONDS,
    BOSS_BROTHERS_WAR_DIVISOR,
    BOSS_BROTHERS_WAR_MAX,
    BOSS_BROTHERS_WAR_MIN,
    BOSS_DURATION_HOURS,
    BOSS_MANAGER_WIN_MULTIPLIER,
    BOSS_MAP,
    BOSS_MARIS_ABSOLUTE_CHANCE,
    BOSS_MARIS_ABSOLUTE_THRESHOLD_DAMAGE,
    BOSS_NIKITA_FRAG_MAX,
    BOSS_NIKITA_FRAG_MIN,
    BOSS_ORG_FRAG_MAX,
    BOSS_ORG_FRAG_MIN,
    BOSS_PARTICIPANT_REWARD,
    BOSS_ROTATION,
    BOSS_SPAWN_HOURS,
    BOSS_TOP_REWARDS,
    MANAGER_DRAIN_OPTIONS,
    MANAGER_DRAIN_PHRASE,
    MANAGER_FAIL_PENALTY,
    MANAGER_HEAL_PHRASE,
    MANAGER_HEAL_THRESHOLD,
    MARIS_DEBUFF_HITS,
    MARIS_DEBUFF_PCT,
    MARIS_FRAG_STEAL_CHANCE,
    MARIS_FRAG_STEAL_MAX,
    MARIS_FRAG_STEAL_MIN,
    MARIS_REBIRTH_PHRASE,
    MARIS_STATIST_STEAL_CHANCE,
    MARIS_STATIST_STEAL_MAX,
    MARIS_STATIST_STEAL_MIN,
    MARIS_SWIM_AWAY_CHANCE,
    MARIS_SWIM_AWAY_HITS,
    MARIS_TOTAL_PHASES,
    ORG_INVISIBLE_HITS,
    ORG_POWER_DEBUFF_MINUTES,
    ORG_POWER_DEBUFF_PCT,
    ORG_SHADOW_PER_HIT,
)
from app.models.boss import ActiveBoss
from app.models.user import User
from app.repositories.boss_repo import boss_repo


# ── Вспомогательные ───────────────────────────────────────────────────────────

def _next_boss_id(last_boss_id: str | None) -> str:
    if last_boss_id is None:
        return BOSS_ROTATION[0]
    try:
        idx = BOSS_ROTATION.index(last_boss_id)
        return BOSS_ROTATION[(idx + 1) % len(BOSS_ROTATION)]
    except ValueError:
        return BOSS_ROTATION[0]


def get_boss_attack_cd(user: User) -> int:
    """Вычисляет КД атаки по боссу с учётом all_cd_reduction."""
    base = BOSS_ATTACK_CD_SECONDS
    reduction_pct = getattr(user, "all_cd_reduction", 0) or 0
    cd = max(BOSS_ATTACK_CD_MIN, int(base * (1 - reduction_pct / 100)))
    return cd


def _compute_boss_reward(boss_id: str, damage: int) -> dict | None:
    """Награда за победу для конкретного участника (поле User + количество).

    Менеджер (умножение монет) и Марис (выдача персонажа) обрабатываются
    отдельно в finalize_boss — их награда не сводится к полю+числу.
    """
    if boss_id == "archangel":
        amt = min(BOSS_ARCHANGEL_FRAG_MAX, max(BOSS_ARCHANGEL_FRAG_MIN, damage // BOSS_ARCHANGEL_FRAG_DIVISOR))
        return {"field": "business_fragments", "amount": amt, "label": "🏢 Фрагменты бизнеса"}
    if boss_id == "brothers":
        amt = min(BOSS_BROTHERS_WAR_MAX, max(BOSS_BROTHERS_WAR_MIN, damage // BOSS_BROTHERS_WAR_DIVISOR))
        return {"field": "war_points", "amount": amt, "label": "⚔️ Очки войны"}
    if boss_id == "nikita":
        return {
            "field": "ui_fragments",
            "amount": random.randint(BOSS_NIKITA_FRAG_MIN, BOSS_NIKITA_FRAG_MAX),
            "label": "🔮 Фрагменты УИ",
        }
    if boss_id == "org":
        return {
            "field": "path_fragments",
            "amount": random.randint(BOSS_ORG_FRAG_MIN, BOSS_ORG_FRAG_MAX),
            "label": "🔷 Фрагменты Пути",
        }
    return None


# ── Сервис ────────────────────────────────────────────────────────────────────

class BossService:

    async def get_current_boss(self, session: AsyncSession) -> ActiveBoss | None:
        return await boss_repo.get_current_boss(session)

    async def get_next_spawn_at(self, session: AsyncSession) -> datetime | None:
        """Возвращает время следующего спавна, если нет активного босса."""
        last = await boss_repo.get_last_boss(session)
        if last and last.next_spawn_at:
            return last.next_spawn_at
        return None

    async def spawn_boss(self, session: AsyncSession) -> ActiveBoss:
        """Спавнит следующего босса по ротации."""
        last = await boss_repo.get_last_boss(session)
        last_boss_id = last.boss_id if last else None
        next_id = _next_boss_id(last_boss_id)
        cfg = BOSS_MAP[next_id]

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=BOSS_DURATION_HOURS)

        # Начальное состояние для каждого типа босса
        if next_id == "nikita":
            state = {"despair_scale": 0.0, "nikita_base": cfg.base_hp, "heal_count": 0}
        elif next_id == "archangel":
            state = {"shield_hp": 0, "debuff_attacks": 0}
        elif next_id == "manager":
            state = {"healed": False}
        elif next_id == "maris":
            state = {"phases_left": MARIS_TOTAL_PHASES, "shield_active": False, "debuffs": {}, "swim_away_left": 0}
        elif next_id == "org":
            state = {"shadow_scale": 0.0, "invisible_left": 0}
        else:
            state = {}

        boss = await boss_repo.create_boss(
            session=session,
            boss_id=next_id,
            hp=cfg.base_hp,
            started_at=now,
            expires_at=expires_at,
            state=state,
        )
        return boss

    async def attack(
        self, session: AsyncSession, user: User, boss: ActiveBoss
    ) -> dict:
        """
        Выполняет атаку игрока по боссу.
        Использует SELECT FOR UPDATE для предотвращения гонок при одновременных атаках.
        Возвращает dict с результатом атаки.
        """
        # Блокируем строку босса
        locked_boss = await boss_repo.get_current_boss_for_update(session)
        if not locked_boss or locked_boss.id != boss.id:
            return {"ok": False, "reason": "Босс уже не активен"}

        cfg = BOSS_MAP.get(locked_boss.boss_id)
        if not cfg:
            return {"ok": False, "reason": "Неизвестный босс"}

        state = locked_boss.get_state()
        base_power = user.combat_power
        phrase = random.choice(cfg.phrases)
        special_effects: list[str] = []
        cd_multiplier: float = 1.0
        coins_drained: int = 0

        # ── Атака Никиты ──────────────────────────────────────────────────────
        if locked_boss.boss_id == "nikita":
            despair = state.get("despair_scale", 0.0)
            nikita_base = state.get("nikita_base", locked_boss.base_max_hp)

            # Урон снижается на % шкалы отчаяния
            damage = max(1, int(base_power * (1 - despair / 100)))

            locked_boss.hp -= damage

            # Увеличиваем шкалу
            despair += NIKITA_DESPAIR_PER_HIT
            state["despair_scale"] = despair

            if despair >= 100:
                # Шкала заполнена: Никита лечится до нового макс HP
                new_base = nikita_base * 2
                locked_boss.hp = new_base
                locked_boss.current_max_hp = new_base
                state["nikita_base"] = new_base
                state["despair_scale"] = 0.0
                state["heal_count"] = state.get("heal_count", 0) + 1
                special_effects.append(
                    f"💢 <b>Шкала отчаяния 100%!</b> Никита восстановил все HP!\n"
                    f"Новый максимум: <b>{_fmt_hp(new_base)}</b>"
                )
            else:
                # Обновляем current_max_hp пропорционально шкале
                locked_boss.current_max_hp = int(nikita_base * (1 + despair / 100))
                special_effects.append(
                    f"🔴 Шкала отчаяния: <b>{despair:.1f}%</b> | "
                    f"Урон снижен до <b>{100 - despair:.0f}%</b>"
                )

        # ── Атака Архангела ───────────────────────────────────────────────────
        elif locked_boss.boss_id == "archangel":
            shield_hp = state.get("shield_hp", 0)
            debuff_attacks = state.get("debuff_attacks", 0)

            damage = base_power
            # Применяем дебафф урона (глобальный)
            if debuff_attacks > 0:
                damage = damage // 2
                state["debuff_attacks"] = debuff_attacks - 1

            # Щит поглощает урон первым
            if shield_hp > 0:
                absorbed = min(shield_hp, damage)
                damage_to_hp = damage - absorbed
                state["shield_hp"] = shield_hp - absorbed
                if state["shield_hp"] <= 0:
                    special_effects.append("🛡 Щит разрушен!")
                locked_boss.hp -= damage_to_hp
                damage = damage_to_hp
            else:
                locked_boss.hp -= damage

            # Рандомный эффект доната
            effects = list(ARCHANGEL_DONATE_WEIGHTS.keys())
            weights = list(ARCHANGEL_DONATE_WEIGHTS.values())
            effect = random.choices(effects, weights=weights, k=1)[0]
            special_effects.append(
                f"💳 <b>Архангел использовал донат:</b> {ARCHANGEL_DONATE_LABELS[effect]}"
            )

            if effect == "heal":
                heal = int(locked_boss.base_max_hp * ARCHANGEL_HEAL_PCT)
                locked_boss.hp = min(locked_boss.current_max_hp, locked_boss.hp + heal)
            elif effect == "shield":
                state["shield_hp"] = int(locked_boss.base_max_hp * ARCHANGEL_SHIELD_PCT)
            elif effect == "debuff":
                state["debuff_attacks"] = state.get("debuff_attacks", 0) + ARCHANGEL_DEBUFF_ATTACKS
            elif effect == "cd":
                cd_multiplier = 2.0

        # ── Атака Менеджера ───────────────────────────────────────────────────
        elif locked_boss.boss_id == "manager":
            damage = base_power
            healed = state.get("healed", False)

            # Слив монет
            drain_pct = random.choice(MANAGER_DRAIN_OPTIONS)
            coins_drained = int(user.nh_coins * drain_pct / 100)
            if coins_drained > 0:
                user.nh_coins = max(0, user.nh_coins - coins_drained)
            special_effects.append(
                f"💸 {drain_pct}% монет слито! (-{_fmt_coins(coins_drained)} NHC)\n"
                f"<i>«{MANAGER_DRAIN_PHRASE}»</i>"
            )

            locked_boss.hp -= damage

            # Проверяем порог <10% для самолечения (один раз)
            if (
                not healed
                and locked_boss.hp > 0
                and locked_boss.hp < locked_boss.base_max_hp * MANAGER_HEAL_THRESHOLD
            ):
                locked_boss.hp = locked_boss.base_max_hp
                state["healed"] = True
                special_effects.append(
                    f"💊 <b>Менеджер восстановил все HP!</b>\n"
                    f"<i>«{MANAGER_HEAL_PHRASE}»</i>"
                )

        # ── Атака Мариса ──────────────────────────────────────────────────────
        elif locked_boss.boss_id == "maris":
            shield_active = state.get("shield_active", False)
            swim_away_left = state.get("swim_away_left", 0)
            debuffs = state.setdefault("debuffs", {})
            user_key = str(user.id)

            if shield_active:
                damage = 0
                state["shield_active"] = False
                special_effects.append("🛡 Щит поглотил атаку полностью!")
            elif swim_away_left > 0:
                damage = 0
                state["swim_away_left"] = swim_away_left - 1
                special_effects.append(
                    f"🌊 «Я уплыл!» Атака не прошла ({state['swim_away_left']} осталось)"
                )
            else:
                damage = base_power
                active_debuff = debuffs.get(user_key, 0)
                if active_debuff > 0:
                    damage = int(damage * (1 - MARIS_DEBUFF_PCT / 100))
                    debuffs[user_key] = active_debuff - 1
                else:
                    debuffs[user_key] = MARIS_DEBUFF_HITS
                    special_effects.append(
                        f"⬇️ Марис снижает твою силу на {MARIS_DEBUFF_PCT}% на {MARIS_DEBUFF_HITS} ударов!"
                    )
                locked_boss.hp -= damage

                # Редкие эффекты (независимые броски, не влияют на урон этого удара)
                if random.randint(1, 100) <= MARIS_FRAG_STEAL_CHANCE:
                    frag_fields = ["ui_fragments", "alchemy_fragments", "path_fragments", "business_fragments"]
                    available = [f for f in frag_fields if getattr(user, f, 0) > 0]
                    if available:
                        field = random.choice(available)
                        amt = min(getattr(user, field), random.randint(MARIS_FRAG_STEAL_MIN, MARIS_FRAG_STEAL_MAX))
                        setattr(user, field, getattr(user, field) - amt)
                        special_effects.append(f"🧩 Марис украл {amt} фрагментов ({field})!")

                if random.randint(1, 100) <= MARIS_STATIST_STEAL_CHANCE:
                    from app.models.squad_member import SquadMember
                    count = random.randint(MARIS_STATIST_STEAL_MIN, MARIS_STATIST_STEAL_MAX)
                    ids_subq = (
                        select(SquadMember.id)
                        .where(SquadMember.user_id == user.id)
                        .order_by(sa_func.random())
                        .limit(count)
                    )
                    del_result = await session.execute(sa_delete(SquadMember).where(SquadMember.id.in_(ids_subq)))
                    removed = del_result.rowcount or 0
                    if removed:
                        from app.repositories.squad_repo import squad_repo
                        await squad_repo.update_user_combat_power(session, user)
                        special_effects.append(f"👥 Марис украл {removed} статистов!")

                if random.randint(1, 100) <= MARIS_SWIM_AWAY_CHANCE:
                    state["swim_away_left"] = MARIS_SWIM_AWAY_HITS
                    special_effects.append(
                        f"🌊 «Я уплыл!» Следующие {MARIS_SWIM_AWAY_HITS} атаки не пройдут урона!"
                    )

        # ── Атака Орга ────────────────────────────────────────────────────────
        elif locked_boss.boss_id == "org":
            invisible_left = state.get("invisible_left", 0)
            shadow_scale = state.get("shadow_scale", 0.0)

            if invisible_left > 0:
                damage = 0
                state["invisible_left"] = invisible_left - 1
                special_effects.append(
                    f"👤 Орг невидим! Атака не прошла ({state['invisible_left']} осталось)"
                )
            else:
                damage = base_power // 2
                locked_boss.hp -= damage
                shadow_scale += ORG_SHADOW_PER_HIT
                if shadow_scale >= 100:
                    state["invisible_left"] = ORG_INVISIBLE_HITS
                    state["shadow_scale"] = 0.0
                    special_effects.append(
                        f"🌑 Шкала тени 100%! Орг уходит в невидимость на {ORG_INVISIBLE_HITS} атак!"
                    )
                else:
                    state["shadow_scale"] = shadow_scale
                    special_effects.append(f"🌑 Шкала тени: {shadow_scale:.0f}%")

            # Постоянные способности — на каждый удар, вне зависимости от невидимости
            cd_multiplier = 2.0
            from app.models.potion import ActivePotion
            session.add(ActivePotion(
                user_id=user.id,
                potion_type="power",
                bonus_value=-ORG_POWER_DEBUFF_PCT,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=ORG_POWER_DEBUFF_MINUTES),
            ))
            special_effects.append(
                f"⬇️ -{ORG_POWER_DEBUFF_PCT}% боевой мощи на {ORG_POWER_DEBUFF_MINUTES} минут!"
            )

        # ── Атака Братьев ─────────────────────────────────────────────────────
        else:  # brothers
            damage = base_power
            # Братья не умирают — HP просто уходит в минус (не обрезаем до 0)
            locked_boss.hp -= damage

        # Братья не могут быть "убиты" в бою; Марис перерождается вместо смерти,
        # пока не исчерпаны все фазы
        boss_defeated = False
        if locked_boss.boss_id == "maris" and locked_boss.hp <= 0:
            phases_left = state.get("phases_left", MARIS_TOTAL_PHASES) - 1
            if phases_left > 0:
                locked_boss.hp = locked_boss.base_max_hp
                locked_boss.current_max_hp = locked_boss.base_max_hp
                state["phases_left"] = phases_left
                state["shield_active"] = True
                phase_num = MARIS_TOTAL_PHASES - phases_left + 1
                special_effects.append(
                    f"🔁 <b>Марис перерождается!</b> Фаза {phase_num}/{MARIS_TOTAL_PHASES}. "
                    f"Щит активен на следующую атаку!\n<i>«{MARIS_REBIRTH_PHRASE}»</i>"
                )
            else:
                locked_boss.hp = 0
                state["phases_left"] = 0
                boss_defeated = True
        elif locked_boss.boss_id != "brothers" and locked_boss.hp <= 0:
            locked_boss.hp = 0
            boss_defeated = True

        # ── Сохраняем состояние ────────────────────────────────────────────────
        locked_boss.set_state(state)

        # ── Обновляем запись атаки ────────────────────────────────────────────
        attack_rec = await boss_repo.get_or_create_attack(
            session, locked_boss.id, user.id
        )
        attack_rec.damage_dealt += damage
        attack_rec.attack_count += 1
        attack_rec.last_attack_at = datetime.now(timezone.utc)

        # ── Если босс побеждён — завершаем прямо сейчас ───────────────────────
        if boss_defeated:
            from datetime import timedelta
            next_spawn = datetime.now(timezone.utc) + timedelta(hours=BOSS_SPAWN_HOURS)
            await boss_repo.finish_boss(session, locked_boss, defeated=True, next_spawn_at=next_spawn)

        await session.flush()

        return {
            "ok": True,
            "damage": damage,
            "boss_hp": locked_boss.hp,
            "boss_max_hp": locked_boss.current_max_hp,
            "boss_base_max_hp": locked_boss.base_max_hp,
            "phrase": phrase,
            "special_effects": special_effects,
            "boss_defeated": boss_defeated,
            "cd_multiplier": cd_multiplier,
            "coins_drained": coins_drained,
            "state": state,
        }

    async def finalize_boss(
        self, session: AsyncSession, boss: ActiveBoss
    ) -> dict:
        """
        Завершает истёкшего босса (вызывается планировщиком).
        Возвращает данные о результате для уведомлений и раздачи наград.
        """
        now = datetime.now(timezone.utc)
        next_spawn = now + timedelta(hours=BOSS_SPAWN_HOURS)

        # Братья: победа только если HP ушло в минус
        if boss.boss_id == "brothers":
            defeated = boss.hp < 0
        else:
            defeated = boss.hp <= 0

        await boss_repo.finish_boss(session, boss, defeated=defeated, next_spawn_at=next_spawn)

        # Раздаём награды участникам
        top = await boss_repo.get_top_attackers(session, boss.id, limit=len(BOSS_TOP_REWARDS))
        all_attackers = await boss_repo.get_all_attackers(session, boss.id)

        top_ids = {rec.user_id for rec in top}
        participant_ids = {rec.user_id for rec in all_attackers}

        rewards: list[dict] = []

        # Топ-5
        for i, rec in enumerate(top):
            base_tickets = BOSS_TOP_REWARDS[i] if i < len(BOSS_TOP_REWARDS) else BOSS_PARTICIPANT_REWARD
            tickets = base_tickets * 2 if defeated else base_tickets
            rewards.append({
                "user_id": rec.user_id,
                "tickets": tickets,
                "damage": rec.damage_dealt,
                "place": i + 1,
            })

        # Остальные участники
        for rec in all_attackers:
            if rec.user_id not in top_ids:
                tickets = BOSS_PARTICIPANT_REWARD * 2 if defeated else BOSS_PARTICIPANT_REWARD
                rewards.append({
                    "user_id": rec.user_id,
                    "tickets": tickets,
                    "damage": rec.damage_dealt,
                    "place": None,
                })

        # Применяем тикеты и награду за победу (своя формула на каждого босса)
        if rewards:
            from sqlalchemy import select as sa_select
            from app.models.user import User as UserModel

            user_ids = [r["user_id"] for r in rewards]
            users_result = await session.execute(
                sa_select(UserModel).where(UserModel.id.in_(user_ids))
            )
            users_map: dict[int, UserModel] = {u.id: u for u in users_result.scalars().all()}

            for r in rewards:
                u = users_map.get(r["user_id"])
                if not u:
                    continue
                from app.config.game_balance import ticket_hard_cap
                u.tickets = min(u.tickets + r["tickets"], ticket_hard_cap(u))

                if not defeated:
                    continue

                if boss.boss_id == "manager":
                    delta = u.nh_coins
                    u.nh_coins = u.nh_coins * BOSS_MANAGER_WIN_MULTIPLIER
                    r["coins_delta"] = delta
                elif boss.boss_id == "maris":
                    from app.data.characters import get_random_character_by_rank
                    from app.models.character import UserCharacter
                    rank = "peak"
                    if (
                        r["damage"] >= BOSS_MARIS_ABSOLUTE_THRESHOLD_DAMAGE
                        and random.randint(1, 100) <= BOSS_MARIS_ABSOLUTE_CHANCE
                    ):
                        rank = "absolute"
                    char = get_random_character_by_rank(rank)
                    if char:
                        session.add(UserCharacter(
                            user_id=u.id,
                            character_id=char["name"],
                            rank=char["rank"],
                            base_power=char["power"],
                            power=char["power"],
                        ))
                        r["character_name"] = char["name"]
                        r["character_rank"] = char["rank"]
                else:
                    res = _compute_boss_reward(boss.boss_id, r["damage"])
                    if res:
                        setattr(u, res["field"], (getattr(u, res["field"], 0) or 0) + res["amount"])
                        r["extra_field"] = res["field"]
                        r["extra_amount"] = res["amount"]

            await session.flush()

            # Персонажи Мариса меняют боевую мощь — пересчитываем после flush
            if boss.boss_id == "maris" and defeated:
                from app.repositories.squad_repo import squad_repo
                for r in rewards:
                    if r.get("character_name"):
                        u = users_map.get(r["user_id"])
                        if u:
                            await squad_repo.update_user_combat_power(session, u)

        cfg = BOSS_MAP.get(boss.boss_id)
        if boss.boss_id == "manager":
            outcome_phrase = cfg.phrases[0] if defeated else MANAGER_FAIL_PHRASE
            if defeated:
                outcome_phrase = "Ебать вы прикольные!"
        elif boss.boss_id == "brothers":
            from app.constants.bosses import BROTHERS_WIN_PHRASE, BROTHERS_FAIL_PHRASE
            outcome_phrase = BROTHERS_WIN_PHRASE if defeated else BROTHERS_FAIL_PHRASE
        elif boss.boss_id == "maris":
            outcome_phrase = MARIS_REBIRTH_PHRASE if defeated else None
        else:
            outcome_phrase = None

        return {
            "defeated": defeated,
            "boss_id": boss.boss_id,
            "boss_name": cfg.name if cfg else boss.boss_id,
            "boss_emoji": cfg.emoji if cfg else "👾",
            "rewards": rewards,
            "participant_count": len(participant_ids),
            "next_spawn_at": next_spawn,
            "outcome_phrase": outcome_phrase,
        }


# ── Утилиты форматирования HP ──────────────────────────────────────────────────

def _fmt_hp(hp: int) -> str:
    ah = abs(hp)
    sign = "-" if hp < 0 else ""
    if ah >= 1_000_000_000_000:
        return f"{sign}{ah / 1_000_000_000_000:.2f}T"
    if ah >= 1_000_000_000:
        return f"{sign}{ah / 1_000_000_000:.2f}B"
    if ah >= 1_000_000:
        return f"{sign}{ah / 1_000_000:.1f}M"
    return f"{sign}{ah:,}"


def _fmt_coins(v: int) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return str(v)


def hp_bar(current: int, maximum: int, length: int = 16) -> str:
    if maximum <= 0:
        return "░" * length
    pct = max(0.0, min(1.0, current / maximum))
    filled = round(pct * length)
    return "█" * filled + "░" * (length - filled)


boss_service = BossService()
fmt_hp = _fmt_hp
fmt_boss_coins = _fmt_coins
