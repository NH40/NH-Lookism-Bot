"""
Бизнес-логика системы Боссов.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.bosses import (
    ARCHANGEL_DEBUFF_ATTACKS,
    ARCHANGEL_DONATE_LABELS,
    ARCHANGEL_DONATE_WEIGHTS,
    ARCHANGEL_HEAL_PCT,
    ARCHANGEL_SHIELD_PCT,
    BOSS_ATTACK_CD_MIN,
    BOSS_ATTACK_CD_SECONDS,
    BOSS_DURATION_HOURS,
    BOSS_MAP,
    BOSS_PARTICIPANT_REWARD,
    BOSS_ROTATION,
    BOSS_SPAWN_HOURS,
    BOSS_TOP_REWARDS,
    MANAGER_DRAIN_OPTIONS,
    MANAGER_DRAIN_PHRASE,
    MANAGER_FAIL_PENALTY,
    MANAGER_HEAL_PHRASE,
    MANAGER_HEAL_THRESHOLD,
    MANAGER_WIN_BONUS,
    NIKITA_DESPAIR_PER_HIT,
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

        # ── Атака Братьев ─────────────────────────────────────────────────────
        else:  # brothers
            damage = base_power
            # Братья не умирают — HP просто уходит в минус (не обрезаем до 0)
            locked_boss.hp -= damage

        # ── Сохраняем состояние ────────────────────────────────────────────────
        locked_boss.set_state(state)

        # Братья не могут быть "убиты" в бою
        boss_defeated = False
        if locked_boss.boss_id != "brothers" and locked_boss.hp <= 0:
            locked_boss.hp = 0
            boss_defeated = True

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
            tickets = BOSS_TOP_REWARDS[i] if i < len(BOSS_TOP_REWARDS) else BOSS_PARTICIPANT_REWARD
            rewards.append({
                "user_id": rec.user_id,
                "tickets": tickets,
                "damage": rec.damage_dealt,
                "place": i + 1,
            })

        # Остальные участники
        for rec in all_attackers:
            if rec.user_id not in top_ids:
                rewards.append({
                    "user_id": rec.user_id,
                    "tickets": BOSS_PARTICIPANT_REWARD,
                    "damage": rec.damage_dealt,
                    "place": None,
                })

        # Применяем тикеты и специальные эффекты (Менеджер)
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
                # Тикеты (для боссов игнорируем ограничение max_tickets)
                u.tickets += r["tickets"]

                # Менеджер: бонус/штраф монетами
                if boss.boss_id == "manager":
                    if defeated:
                        u.nh_coins += MANAGER_WIN_BONUS
                        r["coins_delta"] = MANAGER_WIN_BONUS
                    else:
                        penalty = min(u.nh_coins, MANAGER_FAIL_PENALTY)
                        u.nh_coins = max(0, u.nh_coins - penalty)
                        r["coins_delta"] = -penalty

            await session.flush()

        cfg = BOSS_MAP.get(boss.boss_id)
        if boss.boss_id == "manager":
            outcome_phrase = cfg.phrases[0] if defeated else MANAGER_FAIL_PHRASE
            if defeated:
                outcome_phrase = "Ебать вы прикольные!"
        elif boss.boss_id == "brothers":
            from app.constants.bosses import BROTHERS_WIN_PHRASE, BROTHERS_FAIL_PHRASE
            outcome_phrase = BROTHERS_WIN_PHRASE if defeated else BROTHERS_FAIL_PHRASE
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
