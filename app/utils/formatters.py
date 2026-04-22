def fmt_num(n: int) -> str:
    return f"{n:,}"


def fmt_power(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}М"
    if n >= 1_000:
        return f"{n/1_000:.1f}К"
    return str(n)


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
    }.get(path, path)