"""Единая схема ключей Redis — чтобы не разбредались по хендлерам/сервисам (тот же
принцип, что в Universe Anime Planet).

Доменные ключи (лидерборды king_bot/emperor/gang, кэш file_id карточек и т.п.)
добавляются сюда по мере переноса соответствующего домена, а не заводятся ad-hoc
строками прямо в хендлере/сервисе.
"""
from __future__ import annotations


def action_lock(user_id: int, action: str) -> str:
    """Антидубликат-лок на время обработки одного действия (SET NX PX, правило 2)."""
    return f"lock:{user_id}:{action}"


def tech_mode_flag() -> str:
    return "flag:tech_mode"


def throttle_flag(user_id: int) -> str:
    """Общий антифлуд (см. middlewares/throttling.py) — не путать с action_lock: тот
    защищает конкретное resource-affecting действие от повторного клика (правило 2),
    этот — общий предохранитель от спама любыми апдейтами одного игрока подряд."""
    return f"throttle:{user_id}"


def recruit_extra_cooldown(user_id: int) -> str:
    """КД вербовки статистов (20 минут, raw-notes «Карта») — сам ключ И есть КД
    (`SET NX EX`, правило 4: горячее состояние в Redis, не Postgres-колонка), TTL
    одновременно и защищает от повторного клика (правило 2), и реализует саму игровую
    механику ожидания — второй Redis-лок сверху не нужен."""
    return f"cooldown:recruit_extra:{user_id}"


def train_extras_cooldown(user_id: int) -> str:
    """КД тренировки статистов (30 минут, raw-notes «Карта») — тот же приём, что
    `recruit_extra_cooldown`."""
    return f"cooldown:train_extras:{user_id}"


def cooldown_ready_queue() -> str:
    """ZSET «пуш готовности»: member `uid:вид`, score — unix-время конца КД (`services/cooldown`)."""
    return "queue:cooldown_ready"


def relocate_allowed(user_id: int) -> str:
    """Разрешение сменить страну после пробуждения (`services/awakening.relocate`), с TTL."""
    return f"relocate:allowed:{user_id}"


def free_attack_chain(user_id: int) -> str:
    """Сколько «свободных атак» (без КД) подряд уже выпало — шанс следующей тает
    (`services/district/free_attack`). Сбрасывается первой атакой, поставившей обычный КД."""
    return f"cooldown:free_chain:{user_id}"


def battle_cooldown(user_id: int) -> str:
    """КД на сражения (5м/30м/1ч по фазе, raw-notes «Фазы») — тот же приём `SET NX EX`,
    длительность берётся по фазе игрока в момент атаки (`config/game.BATTLE_COOLDOWN_SECONDS`)."""
    return f"cooldown:battle:{user_id}"


def last_extras_training(user_id: int) -> str:
    """Итог последней тренировки статистов (JSON, TTL сутки) — Mini App показывает его и после
    перезахода на экран."""
    return f"last:extras_training:{user_id}"


def boss_cooldown(user_id: int) -> str:
    """КД боя с боссом события — отдельный от КД сражений за районы (пользователь
    2026-10-11: «атака по боссам не привязана к атаке по районам»)."""
    return f"cooldown:boss:{user_id}"


def sabotage_cooldown(user_id: int, action: str) -> str:
    """КД саботажа (`config/empire.SABOTAGE_COOLDOWN_SECONDS`) — СВОЙ на каждое действие
    (пользователь 2026-10-14), тот же приём `SET NX EX`, что у вербовки: ключ и есть КД."""
    return f"cooldown:sabotage:{user_id}:{action}"


def empire_war_cooldown(user_id: int) -> str:
    """КД объявления войны императоров (`config/empire.EMPIRE_WAR_COOLDOWN_SECONDS`)."""
    return f"cooldown:empire_war:{user_id}"


def empire_war_shield(user_id: int) -> str:
    """Щит императора после итога войны против него — на него нельзя напасть, пока ключ жив."""
    return f"shield:empire_war:{user_id}"


def admin_recent_players(admin_id: int) -> str:
    """Последние открытые админом карточки игроков (список id, свежие слева, до 10)."""
    return f"admin:recent_players:{admin_id}"


def patch_running_flag() -> str:
    """Идёт патч (сброс всех игроков). В Redis, а не в памяти процесса: патч запускают и бот,
    и API Mini App — второй запуск из другого процесса не должен начаться поверх первого."""
    return "flag:admin_patch_running"


def beta_state() -> str:
    """Бета-режим: значение `{эпоха}:{код}`. Нет ключа — беты нет, бот открыт всем.
    Эпоха новая при каждом включении — отсюда сброс всех допусков при выкл/вкл."""
    return "beta:state"


def beta_allowed(epoch: str) -> str:
    """Множество user_id, ввёдших код в ЭТОЙ эпохе беты."""
    return f"beta:allowed:{epoch}"


def beta_attempts(epoch: str, user_id: int) -> str:
    """Счётчик неверных попыток ввода кода (защита от подбора), с TTL окна."""
    return f"beta:attempts:{epoch}:{user_id}"


def card_photo_file_id(card_code: str, version: str) -> str:
    """Telegram `file_id` картинки уника (приём UAP: грузим файл в Telegram один раз, дальше
    шлём по file_id). `version` — время изменения и размер файла: заменили картинку в
    `assets/` — ключ другой, старый file_id больше не используется."""
    return f"card_photo:{card_code}:{version}"


def personal_training_cooldown(user_id: int) -> str:
    """КД личной тренировки (1 час) — сам ключ и есть КД (`SET NX EX`), как у вербовки."""
    return f"cooldown:personal_training:{user_id}"


def gang_delete_confirm(user_id: int) -> str:
    """Подтверждение удаления банды: флаг ставится экраном подтверждения (EX 30 с), кнопка
    «Да» работает только пока он жив — забытое открытым подтверждение само истекает."""
    return f"confirm:gang_delete:{user_id}"


def swap_cooldown(user_id: int, system: str) -> str:
    """КД переключения активной гениальности / уникальной техники / пути (не менять бафы
    перед каждым боем) — `SET NX EX`, ключ и есть КД."""
    return f"cooldown:swap:{system}:{user_id}"


def awaken_confirm(user_id: int) -> str:
    """Подтверждение пробуждения — тот же приём, что у удаления банды (EX N с)."""
    return f"confirm:awaken:{user_id}"


def school_lesson_cooldown(user_id: int, school: str) -> str:
    """КД занятия у учителя статистов — у каждого учителя свой."""
    return f"cooldown:school:{school}:{user_id}"


def casino_bets(user_id: int, game: str, stake: str) -> str:
    """Последние ставки игры одной валютой — детектор стратегии x3 (1.0)."""
    return f"casino:bets:{game}:{user_id}:{stake}"


def blackjack_hand(user_id: int) -> str:
    """Текущая раздача блэкджека (JSON, со ставкой) — TTL: брошенная раздача сгорает."""
    return f"casino:bj:{user_id}"
