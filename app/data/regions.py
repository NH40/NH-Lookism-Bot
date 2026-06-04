from dataclasses import dataclass


@dataclass
class RegionConfig:
    slug: str
    name: str
    emoji: str
    description: str
    owner_bonus_text: str
    member_bonus_text: str

    # % к доходу зданий (income_per_minute)
    owner_income_building_pct: int = 0
    member_income_building_pct: int = 0

    # % к общему доходу (circ + passive)
    owner_income_pct: int = 0
    member_income_pct: int = 0

    # Пассивный доход монет/мин (абсолют)
    owner_passive_income: int = 0
    member_passive_income: int = 0

    # Гений войны (уровень авто-рейдов 1-5, стакается с навыком)
    owner_war_genius: int = 0
    member_war_genius: int = 0

    # КД тренировок у тренеров % снижения
    owner_train_cd_pct: int = 0
    member_train_cd_pct: int = 0

    # КД рейдов % снижения
    owner_raid_cd_pct: int = 0
    member_raid_cd_pct: int = 0

    # Фрагменты в рейдах %
    owner_fragment_pct: int = 0
    member_fragment_pct: int = 0

    # Сила ТОЛЬКО от статистов %
    owner_squad_power_pct: int = 0
    member_squad_power_pct: int = 0

    # Сила ТОЛЬКО от персонажей %
    owner_char_power_pct: int = 0
    member_char_power_pct: int = 0

    # Лимит тикетов ×2 (не меняет шанс!)
    owner_ticket_overflow: bool = False
    member_ticket_overflow: bool = False

    # +1 тикет при успешной прокрутке, 50% шанс (не меняет шанс!)
    owner_double_ticket: bool = False
    member_double_ticket: bool = False

    # Урон в рейдах %
    owner_raid_damage_pct: int = 0
    member_raid_damage_pct: int = 0

    # Скидка у тренеров (Том Ли / Ган / Менеджер Ким) %
    owner_trainer_discount: int = 0
    member_trainer_discount: int = 0


KOREAN_REGIONS: list[RegionConfig] = [

    # ─── ПОНРАВИВШИЕСЯ РЕГИОНЫ ───────────────────────────────────────────────

    RegionConfig(
        slug="seoul",
        name="Сеул",
        emoji="🏙",
        description="Столица — тотальная военная власть для того, кто её держит.",
        owner_bonus_text=(
            "⚙️ Гений войны MAX — все 5 авто-рейдов активны постоянно\n"
            "   (Шинген → Ган → Джинен → Гапрен → Элита)"
        ),
        member_bonus_text="⚙️ Гений войны Ур.1 — авто-атака Шингена",
        owner_war_genius=5,
        member_war_genius=1,
    ),

    RegionConfig(
        slug="incheon",
        name="Инчхон",
        emoji="🌊",
        description="Логистический хаб — тренировки у Тома Ли, Гана и Менеджера Кима и рейды идут быстрее.",
        owner_bonus_text=(
            "⏩ -40% КД тренировок (Том Ли / Ган / Менеджер Ким)\n"
            "⏩ -40% КД рейдов"
        ),
        member_bonus_text="⏩ -10% КД тренировок",
        owner_train_cd_pct=40,
        owner_raid_cd_pct=40,
        member_train_cd_pct=10,
    ),

    RegionConfig(
        slug="gyeongnam",
        name="Южный Кенсан",
        emoji="🌴",
        description="Южные богатства — пассивный доход идёт, пока другие воюют.",
        owner_bonus_text="💰 +7 000 монет/мин пассивно",
        member_bonus_text="💰 +100 монет/мин пассивно",
        owner_passive_income=7000,
        member_passive_income=100,
    ),

    RegionConfig(
        slug="chungbuk",
        name="Северный Чжунчхон",
        emoji="🌲",
        description="Леса скрывают несметные ресурсы — рейды приносят больше и быстрее восстанавливаются.",
        owner_bonus_text=(
            "💎 +60% фрагментов в рейдах\n"
            "⏩ -30% КД рейдов"
        ),
        member_bonus_text="💎 +8% фрагментов в рейдах",
        owner_fragment_pct=60,
        owner_raid_cd_pct=30,
        member_fragment_pct=8,
    ),

    RegionConfig(
        slug="jeonnam",
        name="Южная Чолла",
        emoji="🐉",
        description="Земля дракона — клад огромен, а персонажи обретают запредельную силу.",
        owner_bonus_text=(
            "💎 +50% фрагментов в рейдах\n"
            "🧍 +40% силы ТОЛЬКО от персонажей"
        ),
        member_bonus_text=(
            "💎 +5% фрагментов\n"
            "🧍 +5% силы персонажей"
        ),
        owner_fragment_pct=50,
        owner_char_power_pct=40,
        member_fragment_pct=5,
        member_char_power_pct=5,
    ),

    # ─── НОВЫЕ УНИКАЛЬНЫЕ МЕХАНИКИ ────────────────────────────────────────────

    RegionConfig(
        slug="gyeonggi",
        name="Кёнги",
        emoji="🏞",
        description="Военный гарнизон у столицы — статисты здесь становятся машинами войны.",
        owner_bonus_text=(
            "💪 +60% силы ТОЛЬКО от статистов\n"
            "🏛 +20% дохода зданий"
        ),
        member_bonus_text=(
            "💪 +8% силы статистов\n"
            "🏛 +3% дохода зданий"
        ),
        owner_squad_power_pct=60,
        owner_income_building_pct=20,
        member_squad_power_pct=8,
        member_income_building_pct=3,
    ),

    RegionConfig(
        slug="gangwon",
        name="Канвон",
        emoji="🏔",
        description="Горные воины — сила статистов здесь выходит за пределы возможного.",
        owner_bonus_text="💪 +80% силы ТОЛЬКО от статистов",
        member_bonus_text="💪 +8% силы статистов",
        owner_squad_power_pct=80,
        member_squad_power_pct=8,
    ),

    RegionConfig(
        slug="chungnam",
        name="Южный Чжунчхон",
        emoji="🌾",
        description="Богатейшие угодья — здания приносят в разы больше плюс пассивный поток монет.",
        owner_bonus_text=(
            "🏛 +60% к доходу зданий\n"
            "💰 +5 000 монет/мин пассивно"
        ),
        member_bonus_text=(
            "🏛 +8% к доходу зданий\n"
            "💰 +100 монет/мин пассивно"
        ),
        owner_income_building_pct=60,
        owner_passive_income=5000,
        member_income_building_pct=8,
        member_passive_income=100,
    ),

    RegionConfig(
        slug="sejong",
        name="Сэджон",
        emoji="🏛",
        description="Административный центр — тренеры работают за бесценок, хранилище тикетов безгранично.",
        owner_bonus_text=(
            "🎫 Лимит тикетов ×2 (не меняет шанс!)\n"
            "🏷 -40% стоимость тренировок у Тома Ли / Гана / Менеджера Кима"
        ),
        member_bonus_text="🏷 -10% стоимость тренировок у тренеров",
        owner_ticket_overflow=True,
        owner_trainer_discount=40,
        member_trainer_discount=10,
    ),

    RegionConfig(
        slug="daejeon",
        name="Тэджон",
        emoji="⚡",
        description="Технологический хаб — тренировки мгновенны, а урон в рейдах бьёт с удвоенной силой.",
        owner_bonus_text=(
            "⏩ -60% КД тренировок\n"
            "⚔️ +60% урона в рейдах"
        ),
        member_bonus_text=(
            "⏩ -10% КД тренировок\n"
            "⚔️ +5% урона в рейдах"
        ),
        owner_train_cd_pct=60,
        owner_raid_damage_pct=60,
        member_train_cd_pct=10,
        member_raid_damage_pct=5,
    ),

    RegionConfig(
        slug="gyeongbuk",
        name="Северный Кенсан",
        emoji="⛰",
        description="Крепость элитных воинов — персонажи здесь обретают запредельную силу.",
        owner_bonus_text="🧍 +80% силы ТОЛЬКО от персонажей",
        member_bonus_text="🧍 +8% силы персонажей",
        owner_char_power_pct=80,
        member_char_power_pct=8,
    ),

    RegionConfig(
        slug="daegu",
        name="Тэгу",
        emoji="🔥",
        description="Торговая империя — здания приносят огромный доход, монеты идут рекой.",
        owner_bonus_text="🏛 +80% к доходу зданий",
        member_bonus_text="🏛 +8% к доходу зданий",
        owner_income_building_pct=80,
        member_income_building_pct=8,
    ),

    RegionConfig(
        slug="ulsan",
        name="Ульсан",
        emoji="🏭",
        description="Военно-промышленный комплекс — война гениев на максимуме, статисты сильнее.",
        owner_bonus_text=(
            "⚙️ Гений войны +3 уровня (стакается с навыком)\n"
            "💪 +30% силы статистов"
        ),
        member_bonus_text=(
            "⚙️ Гений войны +1 уровень\n"
            "💪 +5% силы статистов"
        ),
        owner_war_genius=3,
        owner_squad_power_pct=30,
        member_war_genius=1,
        member_squad_power_pct=5,
    ),

    RegionConfig(
        slug="busan",
        name="Пусан",
        emoji="🌅",
        description="Второй по величине порт — пассивный доход течёт круглосуточно.",
        owner_bonus_text="💰 +5 000 монет/мин пассивно",
        member_bonus_text="💰 +50 монет/мин пассивно",
        owner_passive_income=5000,
        member_passive_income=50,
    ),

    RegionConfig(
        slug="jeonbuk",
        name="Северная Чолла",
        emoji="🌿",
        description="Мистический край — удача работает иначе. При каждом успехе есть шанс получить лишний тикет.",
        owner_bonus_text=(
            "🎫 Лимит тикетов ×2 (не меняет шанс!)\n"
            "✨ При успехе: 50% шанс +1 дополнительный тикет"
        ),
        member_bonus_text="💎 +5% фрагментов в рейдах",
        owner_ticket_overflow=True,
        owner_double_ticket=True,
        member_fragment_pct=5,
    ),

    RegionConfig(
        slug="gwangju",
        name="Кванджу",
        emoji="💜",
        description="Культурная столица — доходы со всех источников значительно выше.",
        owner_bonus_text=(
            "🏛 +70% к доходу зданий\n"
            "💰 +3 000 монет/мин пассивно"
        ),
        member_bonus_text=(
            "🏛 +8% к доходу зданий\n"
            "💰 +80 монет/мин пассивно"
        ),
        owner_income_building_pct=70,
        owner_passive_income=3000,
        member_income_building_pct=8,
        member_passive_income=80,
    ),
]

REGION_BY_SLUG: dict[str, RegionConfig] = {r.slug: r for r in KOREAN_REGIONS}
