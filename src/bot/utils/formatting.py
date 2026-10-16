from __future__ import annotations

from html import escape


def esc(text: str) -> str:
    """Экранирует пользовательский текст (имя, юзернейм, название банды) перед вставкой в
    HTML-сообщение — бот работает с parse_mode=HTML по умолчанию, и название банды вида
    "a<b" без этого роняло бы отправку всего экрана ("can't parse entities"), причём не
    только у автора: названия чужих банд показываются на карте города. Портировано из
    Universe Anime Planet."""
    return escape(text, quote=False)


def format_countdown(total_seconds: int) -> str:
    """MM:SS, часы добавляются спереди (H:MM:SS) только когда больше 59 минут —
    портировано из Universe Anime Planet почти дословно (тот же формат КД используют
    вербовка/тренировки/сражения по фазам — везде числа в пределах часа-двух, "112:58"
    читался бы плохо)."""
    total_seconds = max(0, total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_number(value: int) -> str:
    """Разделяет разряды запятыми (2000000 -> "2,000,000") — портировано из Universe
    Anime Planet дословно. Понадобилось, как только статисты стали считаться стопками
    (`Extra.quantity` — `BigInteger`, реалистично сотни миллионов/миллиарды) — без
    разделителей число сливается в нечитаемую цепочку цифр."""
    return f"{value:,}"


def progress_bar(percent: float, *, width: int = 10) -> str:
    """Текстовая полоса ▓/░ (портировано из Universe Anime Planet) — в профиле: путь
    характеристики до Infinity, стадия потенциала, ступени мастерства."""
    percent = max(0.0, min(100.0, percent))
    filled = round(width * percent / 100)
    return "▓" * filled + "░" * (width - filled)


def emoji_bar(percent: float, *, fill: str = "🟩", empty: str = "⬛", width: int = 10) -> str:
    """Полоса из эмодзи, как в LBP 1.0 (задания, пасс)."""
    percent = max(0.0, min(100.0, percent))
    filled = int(width * percent / 100)
    return fill * filled + empty * (width - filled)


def format_duration(total_seconds: int) -> str:
    """«2д 5ч», «5ч 12м», «12м» — крупные остатки времени (сезон, сброс дня)."""
    total_seconds = max(0, int(total_seconds))
    days, rest = divmod(total_seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}д {hours}ч"
    if hours:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"
