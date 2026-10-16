"""Человеческое описание эффектов уровней систем развития (тексты).

Описание уровня собирается из тех же данных, по которым считается эффект (`config/*`),
поэтому текст не может разойтись с механикой. Поле модификатора → фраза; у путей и
родословных поверх этого есть названия способностей (`texts/unique_path`, `texts/bloodline`).
"""
from __future__ import annotations

from bot.constant.characteristic import RANK_LADDER


def _pct(v: float) -> str:
    return f"{round(v * 100):g}%"


# Боевые примитивы (`services/combat/mods.py`).
COMBAT_PHRASES: dict[str, str] = {
    "attack": "+{p} к атаке армии",
    "durability": "+{p} к прочности (ХП) бойцов",
    "reduction": "{p} входящего урона гасится",
    "pierce": "пробитие: {p} брони противника игнорируется",
    "dodge": "+{p} к уклонению",
    "block": "+{p} к блоку",
    "counter": "+{p} к контратаке",
    "flee": "+{p} к спасительному побегу",
    "loss_save": "{p} погибших выживает после боя",
    "sure_hit": "{p} ударов проходит сквозь уклонение и блок",
    "crit_chance": "+{p} к шансу крита",
    "crit_power": "+{p} к силе крита",
    "bleed": "кровотечение: {p} урона бьёт ещё раз в следующем раунде",
    "cleave": "удар по нескольким целям: +{p} к урону",
    "first_strike": "удар до боя: {p} армии противника выбито до первого раунда",
    "suppress": "реакции противника слабее на {p}",
    "heal": "лечение: {p} павших за раунд возвращаются в строй",
    "overcome": "преодоление: атака растёт от полученного урона (+{p} за шаг, сильнее против толпы)",
    "despair": "отчаяние: против более сильных бойцов атака до +{p} и меньше потерь",
    "reflect": "отражение: {p} полученного урона копится и возвращается врагу",
    "absorb_store": "поглощение: {p} входящего урона гасится и копится",
    "absorb_return": "накопленное поглощение возвращается с силой ×{x}",
    "adapt_threshold": "терпение: после потери {p} армии — ответный удар",
    "adapt_bonus": "ответный удар после терпения: +{p} к атаке",
    "adapt_guard": "пока терпишь — ещё {p} урона гасится",
    "rush": "рывок: +{p} к атаке в первые раунды",
    "rush_rounds": "рывок длится {n} раунда",
    "ramp": "разгон: +{p} к атаке с каждым раундом",
    "ramp_cap": "разгон до +{p}",
    "opening": "первый удар боя: +{p} к атаке",
    "chaos": "хаос: {p} шанс в раунд нанести двойной удар и сбить реакции врага",
    "reflect_every": "выброс отражения раз в {n} раунда",
    "no_dodge": "от твоих атак не увернуться",
}

# Небоевые модификаторы (`services/build/mods.py`).
ECO_PHRASES: dict[str, str] = {
    "army_power": "+{p} к мощи каждого бойца армии",
    "income": "+{p} к доходу бизнеса",
    "build_discount": "постройка зданий дешевле на {p}",
    "upgrade_discount": "прокачка бизнеса дешевле на {p}",
    "storage_hours": "хранилище бизнеса +{n} ч",
    "tax_relief": "налог императора меньше на {p}",
    "recruit_cooldown": "вербовка чаще на {p}",
    "recruit_rank_bonus": "потолок ранга вербовки +{n}",
    "recruit_double": "{p} шанс завербовать сразу двоих",
    "extras_training": "+{n} п.п. к шансам тренировки статистов",
    "extras_training_cooldown": "тренировка статистов чаще на {p}",
    "extras_extra_roll": "{p} не прошедших тренировку статистов пробуют ещё раз у другого учителя",
    "dev_points": "+{p} очков развития с личной тренировки",
    "personal_cooldown": "личная тренировка чаще на {p}",
    "mastery_delay": "задания мастерства приходят быстрее на {p}",
    "stat_cost_discount": "ранги характеристик дешевле на {p}",
    "stat_floor": "характеристики не ниже ранга {rank}",
    "ticket_regen": "тикеты восстанавливаются быстрее на {p}",
    "ticket_cap": "хранилище тикетов +{n}",
    "gacha_luck": "{p} шанс поднять редкость выпавшего уника",
    "gacha_free_roll": "{p} шанс, что крутка не потратит тикет",
    "battle_cooldown": "перерыв между боями короче на {p}",
    "sabotage_chance": "+{p} к шансу саботажа",
    "sabotage_cooldown": "перерыв саботажа короче на {p}",
    "sabotage_loot": "+{p} к добыче саботажа",
    "stealth": "скрытность: имя скрыто в отчётах и списках",
    "silent_sabotage": "император не узнаёт даже о попытке саботажа",
    "scout": "разведка {n} ур.: видно {scout}",
    "foresight": "предвидение {n} ур.: прогноз боя",
    "marks": "+{n} метк(и) на игроков",
    "logs": "наблюдение {n} ур.: журнал действий игроков",
    "contract_discount": "контракты статистов дешевле на {p}",
    "contract_duration": "контракты статистов дольше на {p}",
    "fragment_bonus": "+{p} фрагментов с боссов",
    "blood_bonus": "+{p} капель крови за пробуждение",
    "medicine_discount": "уровни гения медицины дешевле на {p}",
    "potion_tier": "🧪 открывает зелья до {roman} тира",
    "potion_discount": "🧪 зелья дешевле на {p}",
    "potion_duration": "🧪 зелья действуют на {p} дольше",
    "potion_power": "🧪 эффекты зелий сильнее на {p}",
    "potion_auto": "🧪 авто-зелья: {n} слота",
    "technique_power": "уникальная техника сильнее на {p}",
    "auto_recruit": "Ультра инстинкт: вербовка сама",
    "auto_train": "Ультра инстинкт: тренировки сами",
    "auto_roll": "Ультра инстинкт: крутка тикетов сама",
}
_SCOUT = {1: "мощь цели", 2: "состав лагерей цели", 3: "билд цели"}


ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")


def _phrase(template: str, value) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return template
    return template.format(
        p=_pct(value) if isinstance(value, float) else value,
        n=f"{value:g}",
        x=f"{value:g}",
        rank=RANK_LADDER[int(value)] if isinstance(value, int) and 0 <= value < len(RANK_LADDER) else value,
        scout=_SCOUT.get(int(value), ""),
        roman=ROMAN[int(value)] if isinstance(value, int) and 0 < value < len(ROMAN) else value,
    )


def describe_spec(spec: dict, special_phrases: dict[str, str] | None = None) -> list[str]:
    """Фразы одного уровня (прибавки этого уровня). `special_phrases` — тексты особых
    механик системы (`special` в конфиге уровня)."""
    lines = []
    for field, value in spec.get("special", {}).items():
        if special_phrases and field in special_phrases and value:
            lines.append(_phrase(special_phrases[field], value))
    for field, value in spec.get("combat", {}).items():
        if field in COMBAT_PHRASES and value:
            lines.append(_phrase(COMBAT_PHRASES[field], value))
    for field, value in spec.get("eco", {}).items():
        if field in ECO_PHRASES and value:
            lines.append(_phrase(ECO_PHRASES[field], value))
    return lines


def describe_level(spec: dict, special_phrases: dict[str, str] | None = None) -> str:
    return "; ".join(describe_spec(spec, special_phrases))
