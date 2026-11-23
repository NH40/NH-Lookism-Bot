"""Приёмы в бою — по 4 своих на технику (утверждено пользователем 2026-11-23, `docs/design/combat_moves.md`).

Приём — перк онлайн-боя на ступени 1 / 4 / 7 / 10 уровня (Приём, Связка, Коронный, Предел). Пассивные бафы техники
от уровней остаются как были — приёмы только добавляются поверх (пользователь: «старые бафы никуда не уходят,
это лишь допы»). Предел техники — мини-игра себе (`power` — насколько усиливает удар идеальная игра).
Коды перков прежние (`tech:<код>:<ступень>`) — наборы игроков не слетают. Числа выравнивает симуляция.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bot.services.combat.mods import CombatMods

# Сила приёмов источника (баланс симуляцией 2026-11-23, `docs/design/combat_moves.md`): множитель их эффектов,
# прибавки урона, ослабления противника и мини-игры. Цель — у каждого источника приёмы дают ~70% побед против того
# же билда без приёмов (было 45–85%). Ключ «вид:код».
MOVE_BOOST: dict[str, float] = {
    "blood:elite": 2.19,
    "blood:gapryong": 0.85,
    "blood:hansu": 1.88,
    "blood:jincheol": 1.7,
    "blood:jinyeong": 2.11,
    "blood:kuroda": 1.31,
    "blood:mujin": 1.3,
    "blood:penguan": 1.25,
    "blood:samdak": 1.16,
    "blood:sophia": 2.11,
    "blood:yamazaki": 1.8,
    "tech:beast": 0.78,
    "tech:blade_hands": 0.82,
    "tech:cqc": 0.78,
    "tech:invisible": 1.85,
    "tech:kyokushin": 0.56,
    "tech:midnight": 1.51,
    "tech:muay_thai": 0.95,
    "tech:ninjutsu": 1.72,
    "tech:overcome": 0.63,
    "tech:taekwondo": 1.8,
}

# Цена и КД по ступеням (Приём, Связка, Коронный, Предел).
MOVE_COST: tuple[int, ...] = (2, 3, 4, 5)
MOVE_COOLDOWN: tuple[int, ...] = (2, 2, 3, 3)


@dataclass(frozen=True, slots=True)
class Move:
    name: str
    about: str
    mods: CombatMods = field(default_factory=CombatMods)  # своё на раунд
    enemy: CombatMods = field(default_factory=CombatMods)  # противнику на раунд
    damage: float = 1.0
    enemy_damage: float = 1.0
    power: float = 0.0  # Предел: сила мини-игры
    first_round_damage: float = 0.0  # урон, если приём в первом раунде боя (вместо `damage`)
    copy_share: float = 0.0  # на раунд копирует эту долю бафов источников противника (Джинена)
    mirror: bool = False  # повторяет последний перк противника (Абсолютная копия)
    energy_gain: int = 0  # +⚡ после применения


M = CombatMods

TECH_MOVES: dict[str, tuple[Move, Move, Move, Move]] = {
    "beast": (
        Move("Рывок зверя", "Урон ×1.3, пробитие 20%.", M(pierce=0.2), damage=1.3),
        Move("Звериная ярость", "Атака +40%, свой блок −10%.", M(attack=0.4, block=-0.1)),
        Move("Хаос стаи", "Шанс хаоса 40%: урон ×2.", M(chaos=0.4)),
        Move("Инстинкт хищника", "Мини-игра: урон до ×2; реакции противника −30%.", M(suppress=0.3), power=1.0),
    ),
    "invisible": (
        Move("Удар из ниоткуда", "Невидимый удар: шанс 60%.", M(phantom_chance=0.6, phantom_power=0.3)),
        Move("Шаг в тень", "Уклонение +20%, шанс крита +15%.", M(dodge=0.2, crit_chance=0.15)),
        Move("Серия невидимок", "Невидимые удары растут вдвое быстрее.", M(phantom_chance=0.3, phantom_power=0.2, phantom_growth=0.9)),
        Move("Абсолютная невидимость", "Мини-игра: урон до ×2; уклонение +30%, сила крита +100%.", M(dodge=0.3, crit_power=1.0), power=1.0),
    ),
    "ninjutsu": (
        Move("Кунай", "Кровотечение 25%.", M(bleed=0.25)),
        Move("Дымовая завеса", "Уклонение +20%, реакции противника −20%.", M(dodge=0.2, suppress=0.2)),
        Move("Яд в ране", "Кровотечение 15%, держится дольше.", M(bleed=0.15, bleed_linger=0.5)),
        Move("Теневое убийство", "Мини-игра: урон до ×2; крит +30%, сила крита +80%.", M(crit_chance=0.3, crit_power=0.8), power=1.0),
    ),
    "overcome": (
        Move("Стиснуть зубы", "Гашение 20%, прочность +15%.", M(reduction=0.2, durability=0.15)),
        Move("Встать снова", "15% павших встают и бьют.", M(revive_strike=0.15)),
        Move("Предел преодолён", "Преодоление от полученного урона сильнее.", M(overcome=0.6)),
        Move("Воля сильнее", "Мини-игра: урон до ×2; спасение павших +20%, прочность +20%.", M(loss_save=0.2, durability=0.2), power=1.0),
    ),
    "kyokushin": (
        Move("Сэйкэн-цуки", "Урон ×1.3, пробитие 25%.", M(pierce=0.25), damage=1.3),
        Move("Стойка дзэнкуцу", "Прочность +30%, блок +10%.", M(durability=0.3, block=0.1)),
        Move("Против сильного", "Бонус против более сильного вдвое.", M(vs_stronger=0.25)),
        Move("Ити-гэки", "Мини-игра: урон до ×2; пробитие 50%.", M(pierce=0.5), power=1.0),
    ),
    "taekwondo": (
        Move("Двойной удар", "Дополнительный удар 50%.", M(multi_hit=0.5)),
        Move("Вертушка", "Удар по нескольким целям +30%, урон перетекает на соседей.", M(cleave=0.3, spill=0.5)),
        Move("Встречный пинок", "Контратака +20%, сила контратак +50%.", M(counter=0.2, counter_power=0.5)),
        Move("Шквал ног", "Мини-игра: урон до ×2; доп. удары +100%, реакции противника −25%.", M(multi_hit=1.0, suppress=0.25), power=1.0),
    ),
    "ma_taesu": (
        Move("Тяжёлый кулак", "Урон ×1.5.", damage=1.5),
        Move("Пробивной", "Пробитие 40%, шанс крита +15%.", M(pierce=0.4, crit_chance=0.15)),
        Move("Гром", "Урон ×1.8.", damage=1.8),
        Move("Один удар — один труп", "Мини-игра: урон до ×2.5; сила крита +200%.", M(crit_power=2.0), power=1.5),
    ),
    "one_step": (
        Move("Шаг вперёд", "20% атаки проходит наверняка.", M(sure_hit=0.2)),
        Move("Первым", "Удар до обмена: выбивает 5% армии противника.", M(first_strike=0.05)),
        Move("Сокращение", "Уклонение +15%, урон ×1.3.", M(dodge=0.15), damage=1.3),
        Move("Один шаг", "В первом раунде боя — урон ×3, позже ×1.5; мини-игра усиливает.", damage=1.5, power=0.5, first_round_damage=3.0),
    ),
    "blade_hands": (
        Move("Порез", "Кровотечение 30%.", M(bleed=0.3)),
        Move("Сквозь броню", "Пробитие 40%.", M(pierce=0.4)),
        Move("Веер лезвий", "Удар по нескольким целям +40%, кровотечение 20%.", M(cleave=0.4, bleed=0.2)),
        Move("Тысяча порезов", "Мини-игра: урон до ×2; кровотечение 60%, держится.", M(bleed=0.6, bleed_linger=0.5), power=1.0),
    ),
    "muay_thai": (
        Move("Колено", "Урон ×1.3, прочность +10%.", M(durability=0.1), damage=1.3),
        Move("Клинч", "Гашение 15%, контратака +15%.", M(reduction=0.15, counter=0.15)),
        Move("Натиск", "Натиск +50% в этом раунде.", M(rush=0.5, rush_rounds=10)),
        Move("Восемь конечностей", "Мини-игра: урон до ×1.8; доп. удары +80%.", M(multi_hit=0.8), power=0.8),
    ),
    "midnight": (
        Move("Взмах", "Урон ×1.25, шанс крита +10%.", M(crit_chance=0.1), damage=1.25),
        Move("Нарастание", "Атака +30% сразу.", M(attack=0.3)),
        Move("Быстрый шаг", "Быстрые шаги — серия ударов.", M(rapid_step=0.75, rapid_cap=3.0)),
        Move("Полночь", "Мини-игра: урон до ×2.2; гашение 15%.", M(reduction=0.15), power=1.2),
    ),
    "cqc": (
        Move("Захват", "Стаки CQC сразу.", M(cqc=0.3, cqc_start=0.1)),
        Move("Болевой", "Кровотечение 30%, пробитие 15%.", M(bleed=0.3, pierce=0.15)),
        Move("Против толпы", "Стаки CQC сильнее на 50%.", M(cqc_boost=0.5)),
        Move("Армейская школа", "Мини-игра: урон до ×2; стаки CQC вдвое сильнее, шанс крита +20%.", M(cqc_boost=1.0, crit_chance=0.2), power=1.0),
    ),
    "seirim": (
        Move("Сбить", "Сбить 30% стаков противника.", M(stack_break=0.3)),
        Move("Бросок", "Захват: 20% армии противника пропускает удар, бросок бьёт.", M(grab_chance=1.0, grab_share=0.2, throw_power=0.3)),
        Move("Оглушение", "Захват 15% армии противника, стаки сбиты.", M(grab_chance=1.0, grab_share=0.15, grab_break=0.3)),
        Move("Сейрим", "Мини-игра: урон до ×2; замедление 30%, бросок вдвое сильнее.", M(slow=0.3, grab_chance=0.5, grab_share=0.15, throw_power=0.6), power=1.0),
    ),
}


# Родословные: Предел — мини-игра противнику (`power` — насколько падает его урон при провале) + свой удар.
# Упрощения против черновика (пользователь согласовал 2026-11-23): у навязанной мини-игры один эффект — урон
# противника; «Подкуп» Пеньгуана — удержание части армии противника на раунд (механизм захвата, без броска).
BLOOD_MOVES: dict[str, tuple[Move, Move, Move, Move]] = {
    "elite": (
        Move("Выучка", "Атака +20%, блок +5%.", M(attack=0.2, block=0.05)),
        Move("Строй элиты", "Гашение 15%, прочность +15%.", M(reduction=0.15, durability=0.15)),
        Move("Приказ", "Урон ×1.4.", damage=1.4),
        Move("Гордость элиты", "Урон ×1.3; противник проходит мини-игру — провал: его урон до −40%.", damage=1.3, power=0.4),
    ),
    "mujin": (
        Move("Удар до боя", "Удар до обмена: выбивает 10% армии противника.", M(first_strike=0.1)),
        Move("Быстрый шаг Муджина", "Урон ×1.5.", damage=1.5),
        Move("Сейрим Муджина", "Сейрим сильнее на 50%, сбить 15% стаков.", M(seirim_boost=0.5, stack_break=0.15)),
        Move("Король Сеула", "Урон ×2; мини-игра противнику — провал: его урон до −50%.", damage=2.0, power=0.5),
    ),
    "jinyeong": (
        Move("Копия", "На раунд копирует 20% бафов противника.", copy_share=0.2),
        Move("Чужая сила", "Атака +30%.", M(attack=0.3)),
        Move("Гений копии", "На раунд копирует 35% бафов противника.", copy_share=0.35),
        Move("Абсолютная копия", "Повторяет последний приём противника; мини-игра противнику — провал: его урон до −40%.", mirror=True, power=0.4),
    ),
    "gapryong": (
        Move("Кулак легенды", "Урон ×1.4.", damage=1.4),
        Move("Несломленный", "Прочность +30%.", M(durability=0.3)),
        Move("Против разрыва", "Преодоление сильнее.", M(overcome=0.5)),
        Move("Первое поколение", "Урон ×2.2; мини-игра противнику — провал: его урон до −50%.", damage=2.2, power=0.5),
    ),
    "yamazaki": (
        Move("Щит клана", "Следующий удар противника гасится на 50%.", M(first_hit_ward=0.5)),
        Move("Тело Ямадзаки", "Прочность +30%.", M(durability=0.3)),
        Move("Кровь якудза", "Гашение 25%.", M(reduction=0.25)),
        Move("Глава клана", "+2⚡; мини-игра противнику — провал: его урон до −50%.", power=0.5, energy_gain=2),
    ),
    "samdak": (
        Move("Удар Самдака", "Урон ×1.4.", damage=1.4),
        Move("Звериная хватка", "Захват 15% армии противника.", M(grab_chance=1.0, grab_share=0.15, throw_power=0.2)),
        Move("Бешенство", "Атака +50%, свой блок −10%.", M(attack=0.5, block=-0.1)),
        Move("Король улиц", "Урон ×2; мини-игра противнику — провал: его урон до −40%.", damage=2.0, power=0.4),
    ),
    "sophia": (
        Move("Отражение", "Отражение полученного урона +20%.", M(reflect=0.2)),
        Move("Адаптация", "Бонус адаптации — уже после первых потерь.", M(adapt_bonus=0.34, adapt_threshold=0.001)),
        Move("Терпение", "Стойкость и атака по раундам вдвое быстрее.", M(endure_attack=0.05, endure_guard=0.02)),
        Move("Система Александровых", "Контратаки вдвое сильнее; мини-игра противнику — провал: его урон до −40%.", M(counter_power=1.0, counter=0.1), power=0.4),
    ),
    "kuroda": (
        Move("Тень Куроды", "Уклонение +20%.", M(dodge=0.2)),
        Move("Удар из тени", "Удар до обмена: выбивает 8% армии противника.", M(first_strike=0.08)),
        Move("Неуловимость", "Половина уклонения не сбивается подавлением, уклонение +10%.", M(dodge_true=0.5, dodge=0.1)),
        Move("Клинок Куроды", "Урон ×2; мини-игра противнику — провал: его урон до −60%.", damage=2.0, power=0.6),
    ),
    "jincheol": (
        Move("Власть", "Атака +25%.", M(attack=0.25)),
        Move("Давление", "Реакции противника −25%.", M(suppress=0.25)),
        Move("Кулак Джинчоля", "Урон ×1.6, пробитие 30%.", M(pierce=0.3), damage=1.6),
        Move("Чеболь", "Урон ×2.2; мини-игра противнику — провал: его урон до −40%.", damage=2.2, power=0.4),
    ),
    "hansu": (
        Move("Учитель", "Уклонение, блок и контратака +5%.", M(dodge=0.05, block=0.05, counter=0.05)),
        Move("Выучка Хансу", "Блок +15%, контратака +10%.", M(block=0.15, counter=0.1)),
        Move("Школа Хансу", "Прочность +25%, гашение 10%.", M(durability=0.25, reduction=0.1)),
        Move("Мастер", "Урон ×1.8; мини-игра противнику — провал: его урон до −50%.", damage=1.8, power=0.5),
    ),
    "penguan": (
        Move("Наёмники", "Урон ×1.3.", damage=1.3),
        Move("Деньги решают", "Урон противника ×0.85.", enemy_damage=0.85),
        Move("Подкуп", "10% армии противника не выходит на раунд.", M(grab_chance=1.0, grab_share=0.1)),
        Move("Монополия", "Урон ×2; мини-игра противнику — провал: его урон до −50%.", damage=2.0, power=0.5),
    ),
}


# Техники мастерства (36): приём (кнопка в бою, цена/КД по ступени дерева) + пассив на весь бой, пока техника изучена
# (пассив — источник «mastery» в билде, `services/build`). Упрощения против черновика: «Чем хуже, тем злее» — атака
# +30% с 20% потерь (адаптация); пассив «Абсолютного копирования» — атака +5% (пассивное копирование — только у пути).
# Сила приёмов техник мастерства (баланс симуляцией 2026-11-23): цель — 65 / 70 / 75% побед по ступеням дерева
# против того же бойца без техники. Не правятся: копирование (Взгляд Йохана, Копирование Даниэля — сила зависит от
# бафов противника) и Несгибаемость Гапрёна (спасение павших — после боя, долей побед не меряется).
MASTERY_BOOST: dict[str, float] = {
    "johan_eye": 0.4,
    "eli_wild": 1.19,
    "gapryong_fist": 0.7,
    "god_eye": 1.25,
    "goo_four_swords": 0.81,
    "heavy_hand": 1.19,
    "jaegyeon_speed": 0.35,
    "jake_step": 0.81,
    "jinyoung_instant": 1.62,
    "johan_choreo": 0.4,
    "johan_shadow": 1.5,
    "killing_intent": 1.62,
    "kim_grips": 1.06,
    "king_fist": 0.56,
    "kyokushin_body": 1.25,
    "mandeok_brute": 0.88,
    "mandeok_quake": 1.56,
    "mandeok_wall": 1.19,
    "moonlight_sword": 1.31,
    "pen_sword": 1.31,
    "pichon_blood": 1.44,
    "seokdu_iron": 0.75,
    "seongji_iron": 1.62,
    "sinu_storm": 0.75,
    "ssireum": 0.88,
    "systema_breath": 1.06,
    "taekkyeon": 0.81,
    "vinjin_kick": 1.12,
    "warren_jkd": 0.94,
    "warren_rush": 1.06,
    "yakuza": 0.88,
    "zack_jab": 1.19,
    "zack_wind": 1.12,
}
MASTERY_MOVE_COST: tuple[int, ...] = (2, 3, 4)
MASTERY_MOVE_COOLDOWN: tuple[int, ...] = (2, 2, 3)

MASTERY_MOVES: dict[str, tuple[Move, CombatMods]] = {
    # Сила
    "ssireum": (Move("Бросок через корпус", "Захват 20% армии противника, бросок бьёт.", M(grab_chance=1.0, grab_share=0.2, throw_power=0.3)), M(durability=0.05)),
    "yakuza": (Move("Без правил", "Урон ×1.3, атака +15%.", M(attack=0.15), damage=1.3), M(ramp=0.03)),
    "mandeok_brute": (Move("Сквозь блок", "Пробитие 40%.", M(pierce=0.4)), M(attack=0.05)),
    "king_fist": (Move("Кулак короля", "Урон ×1.5, пробитие 25%.", M(pierce=0.25), damage=1.5), M(pierce=0.05)),
    "vinjin_kick": (Move("Пробивной пинок", "Урон ×1.4, 25% атаки наверняка.", M(sure_hit=0.25), damage=1.4), M(attack=0.06)),
    "heavy_hand": (Move("Вес тела", "Урон ×1.6.", damage=1.6), M(crit_power=0.15)),
    "gapryong_fist": (Move("Сквозь стену", "Урон ×1.8, пробитие 50%.", M(pierce=0.5), damage=1.8), M(attack=0.06)),
    "mandeok_quake": (Move("Землетрясение", "Захват 20% строя противника, удар по нескольким целям +40%.", M(grab_chance=1.0, grab_share=0.2, cleave=0.4)), M(durability=0.08)),
    "taejin_power": (Move("Выкованная мощь", "Урон ×1.7, гашение 10%.", M(reduction=0.1), damage=1.7), M(attack=0.08, durability=0.05)),
    # Скорость
    "zack_jab": (Move("Джеб", "Удар до обмена: выбивает 4% армии противника.", M(first_strike=0.04)), M(opening=0.1)),
    "jake_step": (Move("Шаг и встречный", "Уклонение +15%, контратака +15%.", M(dodge=0.15, counter=0.15)), M(dodge=0.03)),
    "taekkyeon": (Move("Танец", "Уклонение +20%.", M(dodge=0.2)), M(dodge=0.03)),
    "jaegyeon_speed": (Move("Быстрейший", "Дополнительный удар 60%.", M(multi_hit=0.6)), M(multi_hit=0.04)),
    "johan_choreo": (Move("Связка без пауз", "Доп. удары +40%, урон ×1.2.", M(multi_hit=0.4), damage=1.2), M(multi_hit=0.03)),
    "warren_rush": (Move("Рывок", "Натиск +50% в этом раунде.", M(rush=0.5, rush_rounds=10)), M(rush=0.1, rush_rounds=2)),
    "jinyoung_instant": (Move("За гранью реакции", "Реакции противника −40%.", M(suppress=0.4)), M(suppress=0.05)),
    "johan_shadow": (Move("Остаточный образ", "40% уклонения не сбить подавлением, шанс крита +20%.", M(dodge_true=0.4, crit_chance=0.2)), M(dodge=0.05)),
    "sinu_storm": (Move("Шторм", "Доп. удары +100%.", M(multi_hit=1.0)), M(multi_hit=0.05)),
    # Выносливость
    "kyokushin_body": (Move("Полный контакт", "Прочность +25%.", M(durability=0.25)), M(durability=0.05)),
    "systema_breath": (Move("Дыхание", "Гашение 20%, +1⚡.", M(reduction=0.2), energy_gain=1), M(reduction=0.03)),
    "seokdu_iron": (Move("Железо", "Гашение 25%.", M(reduction=0.25)), M(durability=0.06)),
    "pichon_blood": (Move("Вторая кровь", "15% павших встают и бьют, лечение +5%.", M(revive_strike=0.15, heal=0.05)), M(heal=0.03)),
    "zack_wind": (Move("Встать после нокдауна", "12% павших встают и бьют, урон ×1.2.", M(revive_strike=0.12), damage=1.2), M(loss_save=0.05)),
    "eli_wild": (Move("Чем хуже, тем злее", "Атака +30%, когда потеряно 20% армии и больше.", M(adapt_bonus=0.3, adapt_threshold=0.2)), M(reduction=0.04)),
    "gapryong_will": (Move("Не сломать", "Спасение павших +30%, прочность +20%.", M(loss_save=0.3, durability=0.2)), M(loss_save=0.08)),
    "mandeok_wall": (Move("Стена", "Гашение 35%.", M(reduction=0.35)), M(reduction=0.06)),
    "seongji_iron": (Move("До последнего", "Никто не бежит: побег обеих сторон — 0; прочность +30%.", M(flee=-1.0, durability=0.3), enemy=M(flee=-1.0)), M(durability=0.08)),
    # Техника
    "johan_eye": (Move("Повтор", "На раунд копирует 15% бафов противника.", copy_share=0.15), M(crit_chance=0.03)),
    "kim_grips": (Move("Болевой захват", "Захват 15%, кровотечение 15%.", M(grab_chance=1.0, grab_share=0.15, bleed=0.15)), M(pierce=0.04)),
    "pen_sword": (Move("Клинок из ничего", "30% атаки наверняка, шанс крита +15%.", M(sure_hit=0.3, crit_chance=0.15)), M(sure_hit=0.04)),
    "god_eye": (Move("Читает движения", "Уклонение +20%, реакции противника −20%.", M(dodge=0.2, suppress=0.2)), M(dodge=0.04)),
    "moonlight_sword": (Move("Невидимый удар", "Невидимый удар: шанс 50%.", M(phantom_chance=0.5, phantom_power=0.3)), M(crit_chance=0.05)),
    "warren_jkd": (Move("Перехват", "Контратака +25%, сила контратак +60%.", M(counter=0.25, counter_power=0.6)), M(counter=0.04)),
    "daniel_copy": (Move("Абсолютная копия", "На раунд копирует 30% бафов противника.", copy_share=0.3), M(attack=0.05)),
    "goo_four_swords": (Move("Четыре меча", "Доп. удары +80%, шанс крита +25%.", M(multi_hit=0.8, crit_chance=0.25)), M(crit_chance=0.04, sure_hit=0.02)),
    "killing_intent": (Move("Давление", "Противник проходит мини-игру — провал: его урон до −50%.", power=0.5), M(suppress=0.06)),
}


# Описание приёма из его настоящих чисел (после множителя силы) — иначе текст «урон ×1.5» расходился бы с делом.
_DESC: tuple[tuple[str, str, bool], ...] = (  # поле, подпись, в процентах
    ("attack", "атака", True), ("pierce", "пробитие", True), ("sure_hit", "наверняка", True), ("crit_chance", "шанс крита", True),
    ("crit_power", "сила крита", True), ("multi_hit", "доп. удары", True), ("cleave", "по нескольким целям", True),
    ("bleed", "кровотечение", True), ("dodge", "уклонение", True), ("dodge_true", "уклонение сквозь подавление", True),
    ("block", "блок", True), ("counter", "контратака", True), ("counter_power", "сила контратак", True),
    ("reduction", "гашение", True), ("durability", "прочность", True), ("loss_save", "спасение павших", True),
    ("heal", "лечение", True), ("revive_strike", "павшие встают и бьют", True), ("suppress", "реакции противника −", True),
    ("chaos", "шанс хаоса", True), ("first_strike", "удар до обмена", True), ("first_hit_ward", "щит на удар", True),
    ("grab_share", "захват армии", True), ("stack_break", "сбить стаки", True), ("slow", "замедление", True),
    ("phantom_chance", "невидимый удар", True), ("rush", "натиск", True), ("overcome", "Преодоление", True),
    ("vs_stronger", "против сильного", True), ("cqc_boost", "стаки CQC", True), ("reflect", "отражение", True),
)


def describe(mods: CombatMods, damage: float = 1.0, enemy_damage: float = 1.0, power: float = 0.0, copy_share: float = 0.0,
             minigame: str | None = None, first_round_damage: float = 0.0, energy_gain: int = 0, mirror: bool = False) -> str:
    parts: list[str] = []
    if first_round_damage:
        parts.append(f"в 1-м раунде урон ×{first_round_damage:.2f}".rstrip("0").rstrip("."))
    if abs(damage - 1) >= 0.005:
        parts.append(f"урон ×{damage:.2f}".rstrip("0").rstrip("."))
    if abs(enemy_damage - 1) >= 0.005:
        parts.append(f"урон противника ×{enemy_damage:.2f}".rstrip("0").rstrip("."))
    for name, label, pct in _DESC:
        v = getattr(mods, name, 0.0) or 0.0
        if abs(v) >= 0.005:
            sign = "" if label.endswith("−") else ("+" if v > 0 else "−")
            parts.append(f"{label}{sign}{round(abs(v) * 100)}%" if label.endswith("−") else f"{label} {sign}{round(abs(v) * 100)}%")
    if copy_share:
        parts.append(f"копия {round(copy_share * 100)}% бафов противника")
    if mirror:
        parts.append("повтор последнего приёма противника")
    if energy_gain:
        parts.append(f"+{energy_gain}⚡")
    if minigame == "self" and power:
        parts.append(f"мини-игра: удар до ×{1 + power:.1f}")
    elif minigame == "enemy" and power:
        parts.append(f"мини-игра противнику: провал — его урон до −{round(min(1.0, power) * 100)}%")
    s = ", ".join(parts) or "удар в стиле источника"
    return s[0].upper() + s[1:] + "."
