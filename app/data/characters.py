from dataclasses import dataclass, field
import random


@dataclass(frozen=True)
class CharacterRankConfig:
    rank: str
    label: str
    base_power_min: int
    base_power_max: int
    weight: float  # вес гачи — чем меньше, тем реже


CHARACTER_RANKS: list[CharacterRankConfig] = [
    CharacterRankConfig("member",      "Член банды",           100,     500,     44),
    CharacterRankConfig("boss",        "Глава группировки",    500,     1500,    25),
    CharacterRankConfig("king",        "Король",               1500,    4000,    15),
    CharacterRankConfig("strong_king", "Сильный король",       4000,    10000,   10),
    CharacterRankConfig("gen_zero",    "Нулевое поколение",    10000,   30000,   3),
    CharacterRankConfig("new_legend",  "Новая легенда",        30000,   50000,   1.5),
    CharacterRankConfig("legend",      "Легенда",              50000,   900000,  1),
    CharacterRankConfig("peak",        "Вершина",              1000000, 2000000, 0.49),
    CharacterRankConfig("absolute",    "Абсолют",              5000000, 5000000, 0.01),
]

RANK_CONFIG_MAP: dict[str, CharacterRankConfig] = {
    r.rank: r for r in CHARACTER_RANKS
}

RANK_EMOJI: dict[str, str] = {
    "member":      "⬜",
    "boss":        "🟦",
    "king":        "🟩",
    "strong_king": "🟨",
    "gen_zero":    "🟧",
    "new_legend":  "🟥",
    "legend":      "💜",
    "peak":        "🖤",
    "absolute":    "⭐",
}

CHARACTERS: list[dict] = [
    # Член банды (min 100, max 500)
    {"name": "Logan (Prime)", "rank": "member", "power": 180, "desc": "Главный буллинг первой арки, жировая прослойка как броня."},
    {"name": "Yeowool (Speed №3)", "rank": "member", "power": 150, "desc": "Третий по скорости в команде Circle, по мнению СЧ красивая тянка"},
    {"name": "Kenta (Prime)", "rank": "member", "power": 200, "desc": "Мстит Гану за уничтожение клана, невероятное чувство мести."},
    {"name": "Ryuhei (Base)", "rank": "member", "power": 220, "desc": "Лидер байкеров Канто, чем больше угроза, тем сильнее становится."},
    {"name": "Taejin (Kudo)", "rank": "member", "power": 250, "desc": "Директор 1 филиала Workers, мастер Кудо, враг Вин Джина."},
    {"name": "Warren (CQC)", "rank": "member", "power": 240, "desc": "Лучший боец Hostel, ученик менеджера Кима, удары с остановкой сердца."},
    {"name": "Jerry (Boxing)", "rank": "member", "power": 210, "desc": "Правая рука Джейка, боксёр-берсерк, защищающий лидера любой ценой."},
    {"name": "Hudson (mastery)", "rank": "member", "power": 230, "desc": "Ученик Тхэсу, правая рука как сталь, философия одного удара."},
    {"name": "Xiaolung (Staff)", "rank": "member", "power": 260, "desc": "Директор 3 филиала Workers, мастер невидимого оружия гуань дао."},

    # Глава группировки (min 1500, max 4000)
    {"name": "Jay (Weapon)", "rank": "king", "power": 1800, "desc": "Молчаливый богач, мастер Systema и Kali, использует любые предметы как оружие."},
    {"name": "Vasco (Base)", "rank": "king", "power": 1900, "desc": "Лидер Burn Knuckles, добрый великан с татуировками, ученик Брекдака."},
    {"name": "Vin Jin (Current)", "rank": "king", "power": 2000, "desc": "Носитель очков-велосипед, скрывает лицо, ученик Муджина из Чхонняна."},
    {"name": "Sinu (Current)", "rank": "king", "power": 2500, "desc": "Бывший лидер Big Deal, непобедимый в ближнем бою, пользователь невидимых атак."},
    {"name": "Zack (Base)", "rank": "king", "power": 1700, "desc": "Бывший задира, теперь боксёр с железной волей и техникой Гонсоба."},
    {"name": "Seokdu (Prime)", "rank": "king", "power": 2200, "desc": "Король Соын, мастер ударов головой, проиграл троим из второго поколения."},
    {"name": "Maendeok (Mastery)", "rank": "king", "power": 2100, "desc": "Огромный король, полагается на массу и грубую силу."},
    {"name": "Ryuhei (Kagiroi)", "rank": "king", "power": 2800, "desc": "Режим 'Кагирой' — пик силы Рюхея, неудержимая ярость."},
    {"name": "Vasco (Hero)", "rank": "king", "power": 3000, "desc": "Режим 'Герой' — Васко в своём лучшем состоянии, вдохновлённый Брекдаком."},
    {"name": "Eli (Base)", "rank": "king", "power": 2300, "desc": "Приёмный сын Тома Ли, дикий инстинктивный стиль, лидер Hostel."},
    {"name": "Taesoo (King of ansan)", "rank": "king", "power": 2700, "desc": "Король Ансана, верит только в свою правую руку, сила как ураган."},
    {"name": "Gongseob (One generation)", "rank": "king", "power": 2900, "desc": "Король Тэгу, мастер защиты и железного кулака, наставник Зака."},
    {"name": "Zack (Current)", "rank": "king", "power": 2600, "desc": "Зак после тренировок у Гонсоба, освоил технику 'Один дюйм'."},

    # Нулевое поколение (min 100000, max 150000)
    {"name": "Bakgu (Old)", "rank": "gen_zero", "power": 105000, "desc": "Старый ветеран, друг Муджина, помогает главным героям."},
    {"name": "Gentleman (Old)", "rank": "gen_zero", "power": 110000, "desc": "Загадочный старик, знающий секреты прошлого."},
    {"name": "Beolgu (Prime)", "rank": "gen_zero", "power": 135000, "desc": "Один из сильнейших в нулевом поколении, физический монстр."},
    {"name": "Dalyong (King of pusan)", "rank": "gen_zero", "power": 125000, "desc": "Предыдущий король Пусана, наставник Чинранга."},
    {"name": "Taesoo (Ultimate fist)", "rank": "gen_zero", "power": 115000, "desc": "Молодой Тхэсу, только начинающий свой путь короля."},
    {"name": "Gongseob (One step)", "rank": "gen_zero", "power": 120000, "desc": "Молодой Гонсоб, до потери ноги, быстрее молнии."},
    {"name": "Jaegyeon (King of inchon)", "rank": "gen_zero", "power": 130000, "desc": "Король Инчхона, быстрейший из первого поколения."},
    {"name": "Jinrang (Base)", "rank": "gen_zero", "power": 128000, "desc": "Ученик Гапрёна, король Пусана в базовой форме."},
    {"name": "Choi (Lighting)", "rank": "gen_zero", "power": 118000, "desc": "Бывший член команды Гапрёна, мастер молниеносных атак."},
    {"name": "James (2 mastery)", "rank": "gen_zero", "power": 140000, "desc": "Джеймс Ли с двумя мастерствами, уже легенда."},
    {"name": "Seongji (2 mastery)", "rank": "gen_zero", "power": 132000, "desc": "Владелец двух мастерств, шестипалый король Чхонняна."},

    # Сильный король (min 10000, max 100000)
    {"name": "Lineman (Hidden dragon)", "rank": "strong_king", "power": 15000, "desc": "Бывший член Burn Knuckles, скрытый дракон, неожиданно силён."},
    {"name": "Samuel (Base)", "rank": "strong_king", "power": 25000, "desc": "Сын Гапрёна, жаждет признания, жестокий и амбициозный."},
    {"name": "Jake (Base)", "rank": "strong_king", "power": 28000, "desc": "Сын Гапрёна, лидер Big Deal, врождённый талант лидера."},
    {"name": "OG Daniel (Base)", "rank": "strong_king", "power": 30000, "desc": "Первое тело Дэниэля, после тренировок сильно прокачалось."},
    {"name": "Samuel (Heat)", "rank": "strong_king", "power": 35000, "desc": "Сэмюэль в режиме ярости, теряет контроль, но становится сильнее."},
    {"name": "Eli (Wildess)", "rank": "strong_king", "power": 38000, "desc": "Илай, выпустивший дикость, звериный стиль Тома Ли."},
    {"name": "Samuel (Hormones)", "rank": "strong_king", "power": 45000, "desc": "Сэмюэль с активированными гормонами, пик его силы."},
    {"name": "Jake (Overcome)", "rank": "strong_king", "power": 50000, "desc": "Джейк с техникой преодоления, унаследованной от отца."},
    {"name": "Johan (Drugged)", "rank": "strong_king", "power": 55000, "desc": "Йохан под наркотиками, не чувствует боли, чистая ярость."},
    {"name": "Big daniel (Base)", "rank": "strong_king", "power": 60000, "desc": "Второе тело Дэниэля в базе, уже угроза для любого."},
    {"name": "Johan (Eyedrops)", "rank": "strong_king", "power": 70000, "desc": "Йохан с каплями для глаз, видит идеально, копирует без ограничений."},
    {"name": "OG Daniel (Copy)", "rank": "strong_king", "power": 65000, "desc": "Первое тело Дэниэля, использующее копирование техник."},
    {"name": "Big daniel (Copy)", "rank": "strong_king", "power": 75000, "desc": "Второе тело с копированием, идеальный боевой автомат."},
    {"name": "Jichang (Prime)", "rank": "strong_king", "power": 85000, "desc": "Король Чхончхона, считался сильнейшим из королей первого поколения."},
    {"name": "Yugang (Base)", "rank": "strong_king", "power": 40000, "desc": "Бывший член команды Гапрёна, опытный ветеран."},
    {"name": "Paecheon (Base)", "rank": "strong_king", "power": 42000, "desc": "Таинственный боец, связанный с Хвараном."},
    {"name": "Jinrang (Conviction)", "rank": "strong_king", "power": 90000, "desc": "Чинранг с убеждением, наследие Гапрёна, невероятная мощь."},

    # Новая легенда (min 30000, max 50000)
    {"name": "Johan (Path)", "rank": "new_legend", "power": 38000, "desc": "Йохан, вставший на свой путь, даже слепой — опасен."},
    {"name": "№1 (Full power)", "rank": "new_legend", "power": 42000, "desc": "Номер один из Первого филиала, полная мощь — загадка. Жалко его"},
    {"name": "??? (Police)", "rank": "new_legend", "power": 40000, "desc": "Создатель понятия короля."},
    {"name": "Johan (Infinite copy)", "rank": "new_legend", "power": 48000, "desc": "Бесконечное копирование Йохана — путь, взламывающий пределы."},
    {"name": "Yujae (Dark society)", "rank": "new_legend", "power": 45000, "desc": "Лидер 'Тёмного общества', стратег и боец."},
    {"name": "Jaegyeon (3 mastery)", "rank": "new_legend", "power": 47000, "desc": "На Джэгён с тремя мастерствами — Заразился speedom."},
    {"name": "Paecheon (Dark blood)", "rank": "new_legend", "power": 44000, "desc": "Пэкчхон с тёмной кровью, демоническая сила."},
    {"name": "OG Daniel (Path)", "rank": "new_legend", "power": 41000, "desc": "Первое тело Дэниэля, вставшее на свой путь."},
    {"name": "Paecheon (Hwarang)", "rank": "new_legend", "power": 49000, "desc": "Пэкчхон с мечом Хваранга, режущим чёрные кости."},
    {"name": "Seongji (3 Mastery)", "rank": "new_legend", "power": 50000, "desc": "Сон Джи с тремя мастерствами — пик первого поколения."},
    {"name": "James (3 Mastery)", "rank": "new_legend", "power": 50000, "desc": "Джеймс Ли с тремя мастерствами — абсолютная легенда."},
    {"name": "Jinrang (Awakened)", "rank": "new_legend", "power": 50000, "desc": "Пробуждённый Чинранг, готовый к битве с легендами."},

    # Легенда (min 50000, max 900000)
    {"name": "Elite (old)", "rank": "legend", "power": 180000, "desc": "Бывший второй человек Гапрёна, председатель HNH, мастер невидимых атак."},
    {"name": "Goo (Weapon)", "rank": "legend", "power": 250000, "desc": "Гений оружия, любой предмет — смертоносное оружие."},
    {"name": "Jincheol (Phase 1)", "rank": "legend", "power": 300000, "desc": "Лидер группировки Арес, настоящий мужик, ветеран спецназа."},
    {"name": "Brekdak", "rank": "legend", "power": 350000, "desc": "Легенда муай-тай, наставник Васко, кумир самого Гана."},
    {"name": "Hansu (0%)", "rank": "legend", "power": 400000, "desc": "Мастер тхэквондо, батя Техуна, потерявший контроль над разумом."},
    {"name": "Manager kim (path)", "rank": "legend", "power": 420000, "desc": "Бывший спецназовец, отец-одиночка, встал на путь воина."},
    {"name": "Tom lee (Base)", "rank": "legend", "power": 450000, "desc": "Король улиц, дикий зверь, поднимает авто одной рукой."},
    {"name": "Samdak", "rank": "legend", "power": 480000, "desc": "Легендарный воин, чьи техники считаются эталонными."},
    {"name": "Sophia (Alexander)", "rank": "legend", "power": 500000, "desc": "Телохранитель важного дяди, создатель стиля Alexander Systema."},
    {"name": "Goo (Katana)", "rank": "legend", "power": 550000, "desc": "Гу с катаной — именно она оставила шрамы на груди Гана."},
    {"name": "Gun (Base)", "rank": "legend", "power": 600000, "desc": "Гений боя и тренировок, наследник клана Ямадзаки, чёрная кость."},
    {"name": "Jinyoung (Current)", "rank": "legend", "power": 520000, "desc": "Бывший врач Гапрёна, гений копирования, ныне сломлен."},
    {"name": "Gitae (King of seoul)", "rank": "legend", "power": 620000, "desc": "Отцеубийца, король Сеула, физический монстр."},
    {"name": "OG Daniel (UI)", "rank": "legend", "power": 700000, "desc": "Первое тело Дэниэля в режиме ультра-инстинкта."},
    {"name": "Johan (BD copy + path)", "rank": "legend", "power": 650000, "desc": "Гений копирования God Dog, вставший на свой путь копирующий большого Даниэля."},
    {"name": "Tom lee (Savagery)", "rank": "legend", "power": 680000, "desc": "Том Ли, выпустивший дикость — первобытная ярость."},
    {"name": "Goo (50 styles)", "rank": "legend", "power": 720000, "desc": "Гу, использующий все 50 боевых стилей. Котоые создал за ночь по приколу против Гана."},
    {"name": "Shintaro (UI)", "rank": "legend", "power": 660000, "desc": "Младший брат Сингена, хранитель традиций Ямадзаки в ультра-инстинкте."},
    {"name": "Gun (Mastery)", "rank": "legend", "power": 750000, "desc": "Ган, достигший мастерства во всех аспектах боя."},
    {"name": "Shintaro (Muramasa)", "rank": "legend", "power": 780000, "desc": "Шинтаро с легендарным клинком Мурасамой, режущим чёрные кости."},
    {"name": "Shingen (Lethargic)", "rank": "legend", "power": 800000, "desc": "Великий Шинген после битвы с Гапрёном, потерявший амбиции."},
    {"name": "Gapryong (Base)", "rank": "legend", "power": 820000, "desc": "Великий Гапрён, легенда нулевого поколения в базовой форме."},
    {"name": "Elite (Prime)", "rank": "legend", "power": 830000, "desc": "Один из убийц Гапрёна, пользователь невидимых атак, создатель 10 гениев."},
    {"name": "Tom Lee (Prime)", "rank": "legend", "power": 850000, "desc": "Король улиц в прайме, абсолютный король, передавший дикость Эли."},
    {"name": "Junyong (Prime)", "rank": "legend", "power": 860000, "desc": "Первый пользователь копирования, дядя Дэниэля, владелец всех пределов."},
    {"name": "Baekho (Prime)", "rank": "legend", "power": 870000, "desc": "Отец Джери, правая рука Гапрёна, его меч и опора."},
    {"name": "Shingen (Lethargic TUI)", "rank": "legend", "power": 880000, "desc": "Апатичный Шинген в TUI, спасающий сына ценой жизни."},
    {"name": "Gitae (Prime)", "rank": "legend", "power": 890000, "desc": "Отцеубийца в прайме, физический монстр с техникой отчаяния."},
    {"name": "Goo (Hwarang)", "rank": "legend", "power": 900000, "desc": "Гу с клинком Хваранга, режущим чёрные кости."},
    {"name": "James (Prime)", "rank": "legend", "power": 650000, "desc": "Прайм легенды первого поколения, победивший всех королей."},
    {"name": "Gun (TUI)", "rank": "legend", "power": 700000, "desc": "Монстр в TUI, сражавшийся против всего второго поколения и Гу."},
    {"name": "Gapryong (Awakened)", "rank": "legend", "power": 800000, "desc": "Гапрён, достигший преодоления и познавший свой путь."},
    {"name": "Big Daniel (Mastered UI)", "rank": "legend", "power": 900000, "desc": "Большой Дэниэль в ультра-инстинкте — идеальная техника и энергоэффективность."},

    # Вершина (min 1000000, max 2000000)
    {"name": "Mujin", "rank": "peak", "power": 1000000, "desc": "Легенда Сейрима, отец Вин Джина, подтирался красной запиской Ямадзаки."},
    {"name": "Shingen (Prime)", "rank": "peak", "power": 1300000, "desc": "Прайм главы клана Ямадзаки, истинный ультра-инстинкт."},
    {"name": "Gapryong (Prime)", "rank": "peak", "power": 1500000, "desc": "Прайм легендарного Гапрёна, достигший всего — вся Корея в его власти."},

    # Абсолют
    {"name": "Daniel (Prime)", "rank": "absolute", "power": 5000000, "desc": "Теоретическая сила второго тела Дэниэля — совершенная и всеобъемлющая мощь, за пределами пика."}
]

# Суммарный вес для гачи
TOTAL_WEIGHT: float = sum(
    RANK_CONFIG_MAP[c["rank"]].weight for c in CHARACTERS
)


def get_random_character() -> dict:
    """Взвешенный случайный выбор персонажа для гачи."""
    weights = [RANK_CONFIG_MAP[c["rank"]].weight for c in CHARACTERS]
    return random.choices(CHARACTERS, weights=weights, k=1)[0]