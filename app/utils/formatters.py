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


def _scaled_discount(influence: int, zero_point: int) -> int:
    """-50% при 0 → 0% при zero_point → +50% при 2*zero_point влияния,
    линейная интерполяция между точками, без скачков."""
    if influence <= 0:
        return -50
    if influence < zero_point:
        return round(-50 + (influence / zero_point) * 50)
    return min(50, round(((influence - zero_point) / zero_point) * 50))


def influence_discount_pct(user) -> int:
    """Скидка/наценка в магазине от Влияния — зависит от фазы игры.

    Механика: чем выше влияние, тем больше скидка (до +50%).
    Низкое влияние даёт наценку (до -50%).

    Пороги по фазам:
      - Банда:   -50% при 0 → 0% при 250 → +50% при 500 влияния
      - Король:  -50% при 0 → 0% при 4000 → +50% при 8000 влияния
      - Император: -50% при 0 → 0% при 10000 → +50% при 20000 влияния
    """
    influence = getattr(user, "influence", 0) or 0
    phase = getattr(user, "phase", None)

    zero_points = {"gang": 250, "king": 4000, "emperor": 10000}
    zero_point = zero_points.get(phase)
    if zero_point is None:
        return 0
    return _scaled_discount(influence, zero_point)


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
    """Суммарная скидка на вербовку статистов в магазине.
    
    Собирает скидки из всех источников:
      - Навыки пути (recruit_discount_percent)
      - Гений бизнеса (biz_discount_pct)
      - Влияние (influence_discount_pct)
    
    Ограничивает диапазон [-50%, MAX_RECRUIT_DISCOUNT_PCT],
    чтобы наценка не уходила в бесконечность, а скидка не превышала лимит.
    """
    from app.config.game_balance import MAX_RECRUIT_DISCOUNT_PCT
    
    total = (
        getattr(user, "recruit_discount_percent", 0)
        + biz_discount_pct(user)
        + influence_discount_pct(user)
    )
    
    # Скидка не может быть меньше -50% (наценка) и больше MAX_RECRUIT_DISCOUNT_PCT
    return max(-50, min(total, MAX_RECRUIT_DISCOUNT_PCT))


def apply_biz_discount(user, base_cost: int) -> int:
    """Применяет скидку Гения бизнеса к цене.
    
    Дополнительно: если у игрока есть фрагмент "10 гениев" из сета Чарльз Чоя,
    цена дополнительно делится на 2 (50% скидка поверх основной).
    """
    discount_pct = biz_discount_pct(user)
    cost = int(base_cost * (1 - discount_pct / 100))
    
    # Сет Славы «Чарльз Чой» — 10 гениев: дополнительная скидка 50%
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