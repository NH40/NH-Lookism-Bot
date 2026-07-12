def fmt_num(n: int) -> str:
    return f"{n:,}"


def fmt_power(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}М"
    if n >= 1_000:
        return f"{n/1_000:.1f}К"
    return str(n)


def progress_bar(current: int, maximum: int, length: int = 10) -> str:
    if maximum <= 0:
        return ""
    filled = min(length, round(length * current / maximum))
    return "▓" * filled + "░" * (length - filled)


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