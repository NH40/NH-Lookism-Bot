"""Мини-игры занятий техники и финала мастерства (конфиг, пользователь 2026-11-13).

8 типов игр; у каждой техники свой порядок из 8, уровень = 3 фиксированных этапа, сложность
растёт с уровнем (`d` от 0 до 1). Мастерство вместо Тома Ли — 4 игры, по одной на мастерство.
Параметры уходят клиенту (Mini App) как есть; сервер проверяет время и правдоподобный счёт.
"""
from __future__ import annotations

import math

from bot.constant.unique_technique import (
    TECH_BEAST, TECH_BLADE_HANDS, TECH_CQC, TECH_INVISIBLE, TECH_KYOKUSHIN, TECH_MA_TAESU, TECH_MIDNIGHT,
    TECH_MUAY_THAI, TECH_NINJUTSU, TECH_ONE_STEP, TECH_OVERCOME, TECH_SEIRIM, TECH_TAEKWONDO,
)

G_DOTS, G_RHYTHM, G_COMBO, G_DODGE, G_CHARGE, G_MASH, G_REACTION, G_TRACK = (
    "dots", "rhythm", "combo", "dodge", "charge", "mash", "reaction", "track",
)
STAGES_PER_LEVEL = 3

# Порядок игр техники: первые — её «профиль» (скорость, сила, техника…), они чаще в ранних уровнях.
_SPEED = (G_DOTS, G_REACTION, G_TRACK, G_DODGE, G_RHYTHM, G_COMBO, G_MASH, G_CHARGE)
_POWER = (G_MASH, G_CHARGE, G_RHYTHM, G_REACTION, G_DODGE, G_TRACK, G_COMBO, G_DOTS)
_SKILL = (G_COMBO, G_RHYTHM, G_DODGE, G_TRACK, G_CHARGE, G_DOTS, G_REACTION, G_MASH)
_GRIT = (G_DODGE, G_CHARGE, G_MASH, G_RHYTHM, G_COMBO, G_REACTION, G_DOTS, G_TRACK)
TECH_GAMES: dict[str, tuple[str, ...]] = {
    TECH_INVISIBLE: _SPEED, TECH_CQC: _SPEED, TECH_ONE_STEP: _SPEED, TECH_MIDNIGHT: _SPEED,
    TECH_MA_TAESU: _POWER, TECH_KYOKUSHIN: _POWER, TECH_MUAY_THAI: _POWER, TECH_BEAST: _POWER,
    TECH_TAEKWONDO: _SKILL, TECH_NINJUTSU: _SKILL, TECH_BLADE_HANDS: _SKILL, TECH_SEIRIM: _SKILL,
    TECH_OVERCOME: _GRIT,
}


def tech_stages(code: str, level: int) -> tuple[str, str, str]:
    """3 игры уровня `level` (2–10): сдвиг по кругу — за 10 уровней встречаются все 8."""
    games = TECH_GAMES.get(code, _SKILL)
    i = (level - 2) * STAGES_PER_LEVEL
    return tuple(games[(i + k) % len(games)] for k in range(STAGES_PER_LEVEL))  # type: ignore[return-value]


def difficulty_for_level(level: int) -> float:
    return max(0.0, min(1.0, (level - 2) / 8))


def difficulty_for_stage(stage: int) -> float:
    return max(0.0, min(1.0, (stage - 1) / 9))


def params(game: str, d: float) -> dict:
    """Параметры игры при сложности `d` (0 — легко, 1 — сложно, но проходимо). `seconds` — длительность,
    `need` — сколько нужно набрать, `max_score` — потолок счёта (для проверки)."""
    if game == G_DOTS:  # точки появляются и гаснут — успеть нажать
        n = 14 + round(8 * d)
        gap = 750 - 250 * d
        return {"count": n, "life_ms": int(1300 - 550 * d), "gap_ms": int(gap), "need": math.ceil(n * (0.6 + 0.15 * d)),
                "max_score": n, "seconds": n * gap / 1000}
    if game == G_RHYTHM:  # бегунок — нажать в зелёной зоне
        n = 8
        return {"rounds": n, "zone": round(0.30 - 0.14 * d, 3), "speed": round(0.8 + 0.8 * d, 2), "need": 5 + round(2 * d),
                "max_score": n, "seconds": n * 0.9}
    if game == G_COMBO:  # повторить показанную серию ударов
        return {"rounds": 3, "length": 3 + round(3 * d), "show_ms": int(650 - 250 * d), "need": 3, "max_score": 3, "seconds": 6}
    if game == G_DODGE:  # удар слева/справа — уйти в другую сторону
        n = 14 + round(8 * d)
        warn = 950 - 450 * d
        return {"strikes": n, "warn_ms": int(warn), "max_miss": 4 - round(2 * d), "need": n - (4 - round(2 * d)),
                "max_score": n, "seconds": n * (warn + 300) / 1000}
    if game == G_CHARGE:  # удерживать и отпустить в зелёной полосе
        n = 5
        return {"rounds": n, "band": round(0.22 - 0.10 * d, 3), "fill_ms": int(1400 - 500 * d), "need": 3 + round(d),
                "max_score": n, "seconds": n * 1.0}
    if game == G_MASH:  # шквал ударов — набрать N нажатий за время
        s = 8
        return {"seconds": s, "need": 35 + round(30 * d), "max_score": s * 16}
    if game == G_REACTION:  # дождаться сигнала и ударить, фальстарт — промах
        n = 6
        return {"rounds": n, "window_ms": int(650 - 280 * d), "need": 4 + round(d), "max_score": n, "seconds": n * 1.5}
    if game == G_TRACK:  # движущаяся цель — попасть
        s = 12
        return {"seconds": s, "speed": round(0.25 + 0.45 * d, 2), "size": round(0.20 - 0.08 * d, 3), "need": 8 + round(6 * d),
                "max_score": s * 6}
    raise KeyError(game)


# Мастерство: 4 игры вместо Тома Ли (+1 очко за каждую).
MASTERY_GAMES: dict[str, str] = {"strength": G_MASH, "speed": G_DOTS, "technique": G_COMBO, "endurance": G_DODGE}
# Сила: 20 с шквала, каждое нажатие бьёт долей мощи армии; нужно набить мощь Тома этапа.
MASTERY_STRENGTH_SECONDS = 20
MASTERY_POWER_PER_TAP = 1 / 40  # доля мощи армии за нажатие
MASTERY_TAPS_MIN, MASTERY_TAPS_MAX = 30, 140  # 1,5–7 нажатий в секунду
# Выносливость: 20 ударов мощью Тома; каждый пропущенный снимает `MASTERY_HIT_SHARE` его мощи с армии.
MASTERY_STRIKES = 20
MASTERY_HIT_SHARE = 0.12
MASTERY_MISS_MIN, MASTERY_MISS_MAX = 2, 12

MIN_TIME_SHARE = 0.6  # быстрее этой доли длительности игру пройти нельзя (защита от подделки)
TOKEN_TTL_SECONDS = 15 * 60
