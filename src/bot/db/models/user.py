from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.constant.phase import PHASE_GANG
from bot.db.base import Base


class User(Base):
    """Игрок. `id` — Telegram user id (не суррогатный ключ), тот же паттерн, что в
    Universe Anime Planet — не плодит лишний join на каждый хендлер.

    Игровые поля добавляются по мере переноса каждого домена, не все разом. Пока —
    инфраструктурное ядро (middlewares/ban_check, middlewares/tech_mode, services/admin)
    + онбординг страны/города (домен `start`, см. raw-notes «Карта»): `country_code`/
    `city_id` выставляются ОДНИМ атомарным шагом через
    `db.repositories.user.set_country_and_city` (`UPDATE ... WHERE city_id IS NULL`,
    правило 1) — до этого момента выбор страны/города чисто презентационный (навигация
    между сообщениями в `handlers/start`, ничего не пишет в БД), поэтому оба поля либо
    оба NULL, либо оба заполнены. Повторный онбординг до появления кнопки "сбросить
    банду" в профиле (см. raw-notes «Фазы», ещё не реализована) невозможен. `phase` —
    банда/круг/кулак (см. `constant/phase`), все новые игроки начинают с банды.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Роль в админке (`constant/admin.ROLES`); супер-админы — ADMIN_IDS из .env. `is_admin` — legacy.
    admin_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Временный бан (`is_banned` — бессрочный): до этого момента бот игроку не отвечает.
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ban_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)

    country_code: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("countries.code"), nullable=True
    )
    city_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cities.id"), nullable=True)
    phase: Mapped[str] = mapped_column(String(16), nullable=False, default=PHASE_GANG, server_default=PHASE_GANG)

    # Бизнес (см. `services/business`). NHCoin — отдельная мягкая валюта, не донатная
    # (подтверждено 2026-09-29). Стартовый баланс выставляет `upsert_from_telegram` из
    # `config/game.NH_COINS_STARTING`, server_default — нейтральный схемный 0 (тот же
    # приём, что стартовые тикеты в UAP: игровые числа не живут в db/models).
    # `coins_accrued_at` — до какого момента доход зданий уже зачислен в `nh_coins`.
    # `business_level`/`business_capacity` — глобальная прокачка игрока (0..10).
    nh_coins: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    coins_accrued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    business_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    business_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Характеристики игрока (raw-notes «Профиль»): индекс ранга в `constant/characteristic.
    # RANK_LADDER` (0 = F-, 52 = Infinity), растут за очки развития (`dev_points`) из личной
    # тренировки. Потенциал — одна из 8 стадий (`POTENTIAL_ORDER`), случайно при регистрации
    # (выставляет `upsert_from_telegram`), не прокачивается. Имена колонок — `stat_<код>`,
    # код из `STATS` (см. `db/repositories/characteristic`).
    stat_strength: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stat_speed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stat_endurance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stat_agility: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    potential: Mapped[str | None] = mapped_column(String(16), nullable=True)
    dev_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Мастерство (raw-notes «Профиль»): ступень 0..3 (Стена → Трансцендентность → Мастерство)
    # по Силе, Скорости, Выносливости, Технике. Ступени покупаются у тренера Тома Ли после
    # заданий (см. `services/mastery`).
    mastery_strength: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    mastery_speed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    mastery_endurance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    mastery_technique: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Император (фаза кулака, `docs/design/fist_emperor.md`): общий налог для игроков его
    # городов (10–50%, по умолчанию 10) и сколько всего ему пришло с империи (налоги +
    # пассивные 10%) — для экрана «👑 Империя». У не-императоров не используются.
    empire_tax_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    empire_collected: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    # Родословная (`docs/design/development_systems.md`): код из `constant/bloodline`, выбирается
    # ОДИН раз (при регистрации), дальше меняется только донатом; NULL — ещё не выбрана.
    # Уровень растёт за капли крови. Удаление банды всё это не трогает.
    bloodline: Mapped[str | None] = mapped_column(String(16), nullable=True)
    bloodline_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    blood_drops: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    # Остальные системы развития (`docs/design/development_systems.md`): активные путь /
    # уникальная техника / гениальность (коды; владение и уровни — `user_paths`,
    # `user_techniques`, `user_geniuses`), фрагменты для их прокачки (падают с боссов на
    # карте), стадия пути (0 — нет, 1 — пришло «подтверждение убеждений», 2 — убеждение
    # есть, 3 — путь получен) и уровень пробуждения (пока 0 — реализуется после систем).
    active_path: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Второе тело (донат, `services/donate`): второй активный путь и вторая родословная —
    # их бафы действуют одновременно с первыми (пользователь 2026-10-08).
    second_body: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    active_path2: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bloodline2: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bloodline2_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Донат-валюта: 1 ₽ = 1 коин (ЮKassa через Telegram Payments, как в UAP). Тратится только на
    # чёрном рынке — ускорение развития, не боевая сила.
    donate_coins: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    active_technique: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active_genius: Mapped[str | None] = mapped_column(String(32), nullable=True)
    path_fragments: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    # Очки пути — валюта уровней пути, за активность (`config/unique_path.PATH_POINT_SOURCES`).
    # `path_point_gates` — источник → unix-время последнего засчитанного события (интервал
    # на источник — защита от абуза), одним атомарным UPDATE с начислением.
    path_points: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    # Свитки пропуска (награда Battle Pass): мгновенно выполняют активное задание развития.
    skip_scrolls: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    path_point_gates: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    technique_fragments: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    genius_fragments: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    path_stage: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    awakening_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Тикеты на вербовку уников (см. `services/ticket`): ленивый реген 1 / 30 мин до капа 10.
    # `tickets_updated_at` — якорь регена; на капе "замораживается" на сейчас. Стартовый
    # запас выставляет `upsert_from_telegram` из конфига (server_default — нейтральный 0).
    tickets_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    tickets_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Копилка влияния (2026-10-28): при коронации районы освобождаются — влияние за них переносится
    # сюда и дальше всегда прибавляется к влиянию (иначе у императора оставалось 10). Обнуляется
    # только полным сбросом прогресса (удаление банды, пробуждение). Здания (парламенты) — отдельно.
    influence_banked: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Мощь армии для топа/«/players» — снимок `services.extra.get_army_stats` (живой расчёт —
    # 3 запроса на игрока, сортировать по нему всех нельзя). Пересчёт фоном (`services/top`).
    army_power_cache: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0", index=True)
    # Абсолютные карты (`config/absolute`): перк, выбранный Стилистом, и блок абсолютов Арианом.
    absolute_style_pick: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Путь тренировок: сколько тренировок любого вида сделано на этом пути (КПД, `services/build`).
    training_path_reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    absolute_blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Выключенные игроком категории пушей (`constant/settings.NOTIFY_*`, «⚙️ Настройки →
    # 🔔 Уведомления»). Пусто — всё включено; новая категория у всех сразу включена.
    notify_muted: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False, default=list, server_default="{}")
