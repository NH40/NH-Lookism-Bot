from __future__ import annotations


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
