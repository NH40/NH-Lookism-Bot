def fmt_num(n: int) -> str:
    return f"{n:,}"


def fmt_power(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}М"
    if n >= 1_000:
        return f"{n/1_000:.1f}К"
    return str(n)


def clamp_enemy_power(power: int, viewer_power: int) -> int:
    """Ограничивает отображаемую/используемую в оценке силу противника,
    чтобы аномальные значения (тестовые/служебные аккаунты с намеренно
    завышенной мощью) не показывались игрокам как абсурдные числа
    (например "-6,299,999,989,696"). Не меняет реальный исход боя —
    только оценку "сила противника", которую видит игрок до атаки.
    Потолок растёт вместе с мощью смотрящего, чтобы не устаревать по
    мере прогресса игры."""
    cap = max(viewer_power * 10_000, 100_000)
    return min(power, cap)


def progress_bar(current: int, maximum: int, length: int | None = None) -> str:
    """Звёздный рейтинг (как «Уровень пути: ⭐⭐⭐⭐⭐» — уже был в боте и
    смотрится хорошо), а не полоска из блоков: те либо не рендерились
    частью шрифтов (▓░), либо были нечитаемы цветными эмодзи на тёмной
    теме (🟩⬛). Длина = min(maximum, 5) — для шкал 4/5 звёзды совпадают
    со шкалой один-в-один (4/4 = 4 звезды, не 5), а для шкал побольше
    (например Гений бизнеса 0-10) звёзды не растягиваются в длинную
    полоску, которая переносится на новую строку и ломает вёрстку."""
    if maximum <= 0:
        return ""
    if length is None:
        length = min(maximum, 5)
    filled = min(length, round(length * current / maximum))
    return "⭐" * filled + "☆" * (length - filled)


def fmt_ttl(seconds: int) -> str:
    if seconds <= 0:
        return "готово"
    m, s = divmod(seconds, 60)
    if m:
        return f"{m}м {s}с"
    return f"{s}с"


def phase_label(phase: str) -> str:
    return {
        "gang":     "Банда",
        "king":     "Король",
        "fist":     "Кулак",
        "emperor":  "Император",
    }.get(phase, phase)


def phase_emoji(phase: str) -> str:
    return {
        "gang":    "🏴",
        "king":    "👑",
        "fist":    "✊",
        "emperor": "🏛",
    }.get(phase, "🏴")


def path_label(path: str | None) -> str:
    if not path:
        return "не выбран"
    return {
        "legal":     "⚖️ Легальный",
        "illegal":   "🕶 Нелегальный",
        "political": "🏛 Политика",
    }.get(path, path)


def skill_path_label(path: str | None) -> str:
    if not path:
        return "не выбран"
    return {
        "businessman": "Бизнесмен",
        "romantic":    "Романтик",
        "monster":     "Монстр",
        "shadow":      "Тень",
    }.get(path, path)


def influence_discount_pct(user) -> int:
    """Скидка в магазине от Влияния — разная формула по фазам, кусочно-линейная,
    без скачков (плавный переход от отрицательной скидки к положительной):

    Банда: 0 влияния = 0%, линейно до +25% на 500 влияния (5%/100), дальше плато.
    Король: <1000 влияния = -50% (наценка), плавно растёт до 0% на 4000,
    затем плавно растёт до +25% на 8000, дальше плато."""
    influence = getattr(user, "influence", 0) or 0
    phase = getattr(user, "phase", None)

    if phase == "gang":
        return min(25, round(influence * 25 / 500))

    if phase == "king":
        if influence < 1000:
            return -50
        if influence <= 4000:
            return round(-50 + (influence - 1000) * 50 / 3000)
        if influence <= 8000:
            return round((influence - 4000) * 25 / 4000)
        return 25

    return 0


def biz_discount_pct(user) -> int:
    """Скидка трека "Скидка" Гения бизнеса — действует везде, где тратятся
    игровые ресурсы на прокачку: магазин, крафты рейдов (УИ/Путь/Гений
    медицины/Гений войны), не только сам Гений бизнеса."""
    from app.config.game_balance import BIZ_GENIUS_DISCOUNT_PCT_PER_LEVEL
    return (
        getattr(user, "business_genius_discount_level", 0) * BIZ_GENIUS_DISCOUNT_PCT_PER_LEVEL
        + getattr(user, "building_discount_percent", 0)
    )


def total_recruit_discount_pct(user) -> int:
    """Суммарная скидка на вербовку статистов в магазине: скилл-путь +
    Гений бизнеса + Влияние, зажатая сверху MAX_RECRUIT_DISCOUNT_PCT —
    иначе сумма скидок уходит за 100% и товар становится бесплатным."""
    from app.config.game_balance import MAX_RECRUIT_DISCOUNT_PCT
    total = (
        getattr(user, "recruit_discount_percent", 0)
        + biz_discount_pct(user)
        + influence_discount_pct(user)
    )
    return min(total, MAX_RECRUIT_DISCOUNT_PCT)


def apply_biz_discount(user, base_cost: int) -> int:
    discount_pct = biz_discount_pct(user)
    cost = int(base_cost * (1 - discount_pct / 100))
    if getattr(user, "fame_charles_geniuses", False):
        cost = cost // 2
    return max(1, cost)


def pair_lines(items: list[str], max_len: int = 38) -> list[str]:
    """Группирует пункты по 2 в строку через пробелы, но только если пара
    умещается в max_len символов — иначе длинный пункт переносится и ломает
    видимость колонок, поэтому такие пункты остаются по одному на строку."""
    out = []
    i = 0
    while i < len(items):
        item = items[i]
        if i + 1 < len(items) and len(item) + 3 + len(items[i + 1]) <= max_len:
            out.append(f"{item}   {items[i + 1]}")
            i += 2
        else:
            out.append(item)
            i += 1
    return out