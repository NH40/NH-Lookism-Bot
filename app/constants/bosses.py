"""
Балансные константы системы Боссов.
Все числа вынесены сюда — меняй свободно.
"""
from dataclasses import dataclass

# ── Глобальные настройки ──────────────────────────────────────────────────────

# Через сколько часов появляется новый босс после завершения предыдущего
BOSS_SPAWN_HOURS: int = 6

# Сколько часов есть у игроков на победу
BOSS_DURATION_HOURS: int = 3

# Базовый КД атаки по боссу (секунды)
BOSS_ATTACK_CD_SECONDS: int = 600  # 10 минут

# Минимальный КД атаки по боссу после всех бонусов
BOSS_ATTACK_CD_MIN: int = 60  # 1 минута

# ── Награды ───────────────────────────────────────────────────────────────────

# Тикеты для топ-5 игроков по нанесённому урону
BOSS_TOP_REWARDS: list[int] = [100, 80, 50, 40, 25]

# Тикеты всем участникам (игнорируют max_tickets)
BOSS_PARTICIPANT_REWARD: int = 10

# ── Ротация боссов (по порядку) ────────────────────────────────────────────────
BOSS_ROTATION: list[str] = ["nikita", "archangel", "manager", "brothers"]

# ── Никита ────────────────────────────────────────────────────────────────────

NIKITA_BASE_HP: int = 880_000_000_000  # 880 млрд

# На сколько % заполняется шкала отчаяния за 1 удар (0.5 = 200 ударов до 100%)
NIKITA_DESPAIR_PER_HIT: float = 0.5

NIKITA_PHRASES: list[str] = [
    "Вкусно...",
    "Кормите меня!",
    "Познайте отчаяние!",
    "Давайте сыграем!",
]

# ── Архангел ─────────────────────────────────────────────────────────────────

ARCHANGEL_BASE_HP: int = 660_000_000_000  # 660 млрд

# Веса эффектов «доната» (сумма = 100)
ARCHANGEL_DONATE_WEIGHTS: dict[str, int] = {
    "heal":    40,  # Восстановление 5% HP
    "cd":      30,  # Удваивает КД атакующего
    "debuff":  25,  # Снижает урон по боссу вдвое на 10 атак (глобально)
    "shield":   5,  # Щит = 50% max HP (редкий)
}

ARCHANGEL_HEAL_PCT: float     = 0.05   # 5% от base_max_hp
ARCHANGEL_SHIELD_PCT: float   = 0.50   # 50% от base_max_hp
ARCHANGEL_DEBUFF_ATTACKS: int = 10     # количество атак с пониженным уроном

ARCHANGEL_PHRASES: list[str] = [
    "Летс Гоу!",
    "Ехала!",
    "Циферки... как я люблю циферки...",
]

ARCHANGEL_DONATE_LABELS: dict[str, str] = {
    "heal":   "💊 Восстановил 5% HP!",
    "cd":     "⏳ Удвоил твой КД атаки!",
    "debuff": "⬇️ Урон по боссу снижен вдвое на 10 атак!",
    "shield": "🛡 Поставил щит 50% HP!",
}

# ── Менеджер ─────────────────────────────────────────────────────────────────

MANAGER_BASE_HP: int = 890_000_000_000  # 890 млрд

# Возможные % слива NHCoin у атакующего за удар
MANAGER_DRAIN_OPTIONS: list[int] = [5, 10, 15, 20]

# Порог HP для одноразового самолечения
MANAGER_HEAL_THRESHOLD: float = 0.10  # 10%

# Монеты при победе / поражении (всем участникам)
MANAGER_WIN_BONUS: int    = 1_000_000
MANAGER_FAIL_PENALTY: int = 10_000_000

MANAGER_PHRASES: list[str] = [
    "Купите донат)",
    "Я справедливый!",
    "Ещё рады? Купите донат?",
]

MANAGER_DRAIN_PHRASE: str = "вы задонатили Менеджеру, за что он позволяет себя убивать"
MANAGER_HEAL_PHRASE: str  = "Хрен вам, а не светлое будущее!"
MANAGER_WIN_PHRASE: str   = "Ебать вы прикольные!"
MANAGER_FAIL_PHRASE: str  = "Ебать вы лохи!"

# ── Братья ───────────────────────────────────────────────────────────────────

BROTHERS_BASE_HP: int = 2_000_000_000_000  # 2 трлн

BROTHERS_WIN_PHRASE: str  = "Хрень с вами, вы прикольные..."
BROTHERS_FAIL_PHRASE: str = "Хуйтата!"

# ── Описания боссов ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BossConfig:
    boss_id: str
    name: str
    emoji: str
    base_hp: int
    desc: str
    special_desc: str
    phrases: list[str]


BOSSES: list[BossConfig] = [
    BossConfig(
        boss_id="nikita",
        name="Никита",
        emoji="😈",
        base_hp=NIKITA_BASE_HP,
        desc="Могущественный противник с бездонной жаждой отчаяния.",
        special_desc=(
            f"🔴 <b>Шкала отчаяния</b>: каждый удар +{NIKITA_DESPAIR_PER_HIT}% шкалы.\n"
            f"Урон снижается на % шкалы. При 100% — лечится до нового макс. HP!"
        ),
        phrases=NIKITA_PHRASES,
    ),
    BossConfig(
        boss_id="archangel",
        name="Архангел",
        emoji="👼",
        base_hp=ARCHANGEL_BASE_HP,
        desc="Существо из другого мира, живущее на донаты.",
        special_desc=(
            "💳 <b>Система донатов</b>: каждый удар активирует рандомный эффект:\n"
            "• Лечение 5% HP\n• Щит 50% HP (редко)\n"
            "• Удваивает твой КД\n• –50% урона на 10 атак"
        ),
        phrases=ARCHANGEL_PHRASES,
    ),
    BossConfig(
        boss_id="manager",
        name="Менеджер",
        emoji="💼",
        base_hp=MANAGER_BASE_HP,
        desc="Хозяин ситуации. Берёт деньги даже в бою.",
        special_desc=(
            f"💸 <b>Слив монет</b>: каждый удар стоит {'/'.join(str(x) for x in MANAGER_DRAIN_OPTIONS)}% ваших NHCoin.\n"
            f"При &lt;10% HP — один раз восстанавливает все HP.\n"
            f"Победа: +1M монет всем. Поражение: –10M монет всем."
        ),
        phrases=MANAGER_PHRASES,
    ),
    BossConfig(
        boss_id="brothers",
        name="СЧ и НХ",
        emoji="👥",
        base_hp=BROTHERS_BASE_HP,
        desc="Братья. Победить их «по правилам» — невозможно.",
        special_desc=(
            "♾️ <b>Неуязвимы</b>: HP уходит в минус, но они не умирают.\n"
            "Если за 3 часа HP ушло в минус — признают вас достойными!"
        ),
        phrases=[BROTHERS_WIN_PHRASE, BROTHERS_FAIL_PHRASE],
    ),
]

BOSS_MAP: dict[str, BossConfig] = {b.boss_id: b for b in BOSSES}
