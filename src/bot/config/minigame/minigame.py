"""Мини-игры занятий техники и финала мастерства (конфиг, пользователь 2026-11-13).

Уровень техники = 3 фиксированных этапа, сложность растёт с уровнем (`d` от 0 до 1). Мастерство вместо Тома
Ли — 4 игры, по одной на мастерство. Параметры уходят клиенту (Mini App) как есть; сервер проверяет время и
правдоподобный счёт.

2026-11-23 (пользователь): 21 механика, у каждой ОДНА версия (варианты «быстрый/плотный/точный/долгий/жёсткий»
убраны); у техники 8 игр из её профиля, повторы между техниками разрешены.
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
G_ORDER, G_ARROWS, G_WHACK, G_COUNT, G_PAIRS, G_STANCE, G_BREATH, G_AIM, G_PARRY, G_CHAIN, G_HOLD, G_GONOGO, G_SPLIT = (
    "order", "arrows", "whack", "count", "pairs", "stance", "breath", "aim", "parry", "chain", "hold", "gonogo", "split",
)
ALL_GAMES: tuple[str, ...] = (
    G_DOTS, G_RHYTHM, G_COMBO, G_DODGE, G_CHARGE, G_MASH, G_REACTION, G_TRACK,
    G_ORDER, G_ARROWS, G_WHACK, G_COUNT, G_PAIRS, G_STANCE, G_BREATH, G_AIM, G_PARRY, G_CHAIN, G_HOLD, G_GONOGO, G_SPLIT,
)
STAGES_PER_LEVEL = 3
GAMES_PER_TECH = 8

_PROFILE: dict[str, tuple[str, ...]] = {  # профиль техники — какие механики ей ближе (первые — чаще)
    "speed": (G_DOTS, G_REACTION, G_CHAIN, G_SPLIT, G_ARROWS, G_TRACK, G_PARRY, G_DODGE, G_GONOGO, G_WHACK),
    "power": (G_MASH, G_CHARGE, G_HOLD, G_BREATH, G_WHACK, G_RHYTHM, G_AIM, G_REACTION, G_PARRY, G_CHAIN),
    "skill": (G_COMBO, G_ORDER, G_PAIRS, G_STANCE, G_COUNT, G_ARROWS, G_RHYTHM, G_AIM, G_TRACK, G_SPLIT),
    "grit": (G_DODGE, G_HOLD, G_PARRY, G_BREATH, G_GONOGO, G_CHARGE, G_COUNT, G_MASH, G_STANCE, G_ORDER),
}
_TECH_PROFILE: tuple[tuple[str, str], ...] = (
    (TECH_INVISIBLE, "speed"), (TECH_MA_TAESU, "power"), (TECH_TAEKWONDO, "skill"), (TECH_OVERCOME, "grit"),
    (TECH_CQC, "speed"), (TECH_KYOKUSHIN, "power"), (TECH_NINJUTSU, "skill"), (TECH_ONE_STEP, "speed"),
    (TECH_MUAY_THAI, "power"), (TECH_BLADE_HANDS, "skill"), (TECH_MIDNIGHT, "speed"), (TECH_BEAST, "power"), (TECH_SEIRIM, "skill"),
)
_FALLBACK = (G_COMBO, G_RHYTHM, G_DODGE, G_TRACK, G_CHARGE, G_DOTS, G_REACTION, G_MASH)


def _assign() -> dict[str, tuple[str, ...]]:
    """8 игр техники — из списка её профиля (10 механик), сдвиг по кругу на 2 для каждой следующей техники
    того же профиля: наборы и порядок у «соседей» по профилю не совпадают. Повторы между техниками разрешены
    (пользователь 2026-11-23)."""
    out: dict[str, tuple[str, ...]] = {}
    seen: dict[str, int] = {}
    for tech, profile in _TECH_PROFILE:
        games = _PROFILE[profile]
        shift = 2 * seen.get(profile, 0)
        seen[profile] = seen.get(profile, 0) + 1
        out[tech] = tuple(games[(shift + i) % len(games)] for i in range(GAMES_PER_TECH))
    return out


TECH_GAMES: dict[str, tuple[str, ...]] = {}


def tech_stages(code: str, level: int) -> tuple[str, str, str]:
    """3 игры уровня `level` (2–10): сдвиг по кругу — за 10 уровней встречаются все 8."""
    if not TECH_GAMES:
        TECH_GAMES.update(_assign())
    games = TECH_GAMES.get(code, _FALLBACK)
    i = (level - 2) * STAGES_PER_LEVEL
    return tuple(games[(i + k) % len(games)] for k in range(STAGES_PER_LEVEL))  # type: ignore[return-value]


def difficulty_for_level(level: int) -> float:
    return max(0.0, min(1.0, (level - 2) / 8))


def difficulty_for_stage(stage: int) -> float:
    return max(0.0, min(1.0, (stage - 1) / 9))


def params(game: str, d: float) -> dict:
    """Параметры игры при сложности `d`. Старый код «механика~вариант» (варианты убраны 2026-11-23) —
    берётся только механика."""
    base = game.partition("~")[0]
    p = _base_params(base, d)
    p["need"] = min(p["need"], p["max_score"])
    p = _playable(base, p)
    p["min_seconds"] = round(_min_seconds(base, p), 2)
    return p


_TIMED = frozenset({G_MASH, G_CHAIN, G_TRACK, G_HOLD})  # идут ровно по таймеру
_MIN_UNIT_S = 0.25  # быстрее одного осмысленного действия за 250 мс человек не играет


def _min_seconds(game: str, p: dict) -> float:
    """Нижняя граница честной длительности (2026-11-23): раньше сервер требовал ≥60% от `seconds`, а многие игры
    заканчиваются по ответу игрока (пары, порядок, стрелки, заряд…) — быстрый игрок получал «слишком быстро»."""
    if game in _TIMED:
        return p["seconds"] * 0.9
    if game == G_PAIRS:
        return p["pairs"] * 2 * _MIN_UNIT_S
    if game == G_COMBO:  # показ серии идёт сам: 0.5 с + (показ + пауза) на удар
        return p["rounds"] * (0.5 + p["length"] * (p["show_ms"] + p.get("gap_ms", 150)) / 1000)
    if game == G_ORDER:
        return p["rounds"] * p["length"] * _MIN_UNIT_S
    if game == G_REACTION:  # ожидание сигнала не короче 0.9 с + пауза 0.5 с
        return p["rounds"] * 1.4
    if game in (G_DODGE, G_SPLIT, G_WHACK):  # таймлайн фиксирован, ответ раунд не укорачивает
        units = p.get("strikes") or p.get("count")
        per = (p.get("warn_ms") or p.get("life_ms")) / 1000
        return units * per * 0.8
    units = p.get("count") or p.get("rounds") or p.get("strikes") or 1
    return units * _MIN_UNIT_S


# Играбельность (аудит 2026-11-20): после сложности и варианта — человеческие пороги на телефоне.
_MS_FLOOR = {"window_ms": 350, "warn_ms": 450, "flash_ms": 350, "show_ms": 350, "life_ms": 500, "gap_ms": 350,
             "round_ms": 3000, "fill_ms": 700}
_SIZE_FLOOR = {"zone": 0.12, "band": 0.10, "size": 0.10}
_TIMING_WINDOW_S = 0.12  # цель/полоса проходит зону не быстрее, чем за 120 мс
_NO_SLACK = frozenset({G_MASH, G_HOLD, G_CHAIN, G_TRACK, G_PAIRS})  # счёт по времени/всё поле — свой предел


def _playable(game: str, p: dict) -> dict:
    p = dict(p)
    for k, lo in _MS_FLOOR.items():
        if k in p:
            p[k] = max(lo, p[k])
    for k, lo in _SIZE_FLOOR.items():
        if k in p:
            p[k] = max(lo, p[k])
    if game == G_REACTION:  # сигнал → касание на телефоне: реакция ~300 мс + задержка экрана
        p["window_ms"] = max(450, p["window_ms"])
    if game == G_DODGE:  # инверсия (жать в другую сторону) медленнее простой реакции
        p["warn_ms"] = max(550, p["warn_ms"])
    if game == G_RHYTHM:  # бегунок: speed — долей полосы в секунду
        p["speed"] = min(p["speed"], round(p["zone"] / _TIMING_WINDOW_S, 2))
    if game == G_AIM:  # прицел ходит туда-обратно: 2·speed долей в секунду
        p["speed"] = min(p["speed"], round(p["size"] / (2 * _TIMING_WINDOW_S), 2))
    if game == G_TRACK:
        p["speed"] = min(p["speed"], 0.8)
    if game == G_CHARGE:  # окно отпускания = band × fill_ms
        p["fill_ms"] = max(p["fill_ms"], int(_TIMING_WINDOW_S * 1000 / p["band"]))
    if game == G_MASH:  # не больше ~7 нажатий в секунду
        p["need"] = min(p["need"], int(7 * p["seconds"]))
    if game == G_HOLD:  # не больше 70% времени в зоне
        p["need"] = min(p["need"], int(p["seconds"] * 10 * 0.6))  # было 70% — на «жёстком» почти недостижимо
    if game not in _NO_SLACK:  # идеал не обязателен: хотя бы 1 ошибка (≈12%) допустима
        p["need"] = max(1, min(p["need"], p["max_score"] - max(1, math.ceil(p["max_score"] * 0.12))))
    if "max_miss" in p:  # экран «пропущено x/N» — ровно столько, сколько реально можно пропустить
        p["max_miss"] = p["max_score"] - p["need"]
    return p


def _base_params(game: str, d: float) -> dict:
    """Параметры механики при сложности `d` (0 — легко, 1 — сложно, но проходимо). `seconds` — длительность,
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
    if game == G_ORDER:  # нажать кружки по порядку 1..N, несколько раундов
        r = 4
        return {"rounds": r, "length": 4 + round(2 * d), "round_ms": int(5000 - 1500 * d), "need": 3, "max_score": r, "seconds": r * 3.5}
    if game == G_ARROWS:  # стрелка — нажать такую же из четырёх
        n = 12
        return {"rounds": n, "window_ms": int(1300 - 600 * d), "need": 8 + round(2 * d), "max_score": n, "seconds": n * 1.0}
    if game == G_WHACK:  # сетка 3×3: красных бить, синих не трогать
        n = 16
        decoys = round(n * (0.25 + 0.15 * d))  # ровно столько синих (раньше — случайно, целей могло не хватить)
        reals = n - decoys
        # max_score — все n (потолок для проверки и для старого клиента со случайными синими по `decoy`)
        return {"count": n, "life_ms": int(1000 - 400 * d), "decoys": decoys, "decoy": round(decoys / n, 2),
                "need": math.ceil(reals * (0.7 + 0.1 * d)), "max_score": n, "seconds": n * 0.9}
    if game == G_COUNT:  # сосчитать вспышки
        n = 5
        return {"rounds": n, "flashes": 4 + round(4 * d), "flash_ms": int(450 - 200 * d), "need": 3 + round(d), "max_score": n,
                "seconds": n * 4}
    if game == G_PAIRS:  # найти пары карточек
        n = 4 + round(2 * d)
        return {"pairs": n, "seconds": 30 - 6 * d, "need": n, "max_score": n}
    if game == G_STANCE:  # показали стойку — выбрать такую же из трёх
        n = 10
        return {"rounds": n, "window_ms": int(1600 - 700 * d), "need": 7 + round(d), "max_score": n, "seconds": n * 1.2}
    if game == G_BREATH:  # круг дышит — нажать на вдохе (в самом большом)
        n = 6
        return {"rounds": n, "zone": round(0.22 - 0.1 * d, 3), "speed": round(0.7 + 0.6 * d, 2), "need": 4 + round(d),
                "max_score": n, "seconds": n * 2}
    if game == G_AIM:  # прицел ходит — остановить в мишени (мишень каждый раз на новом месте)
        n = 6
        return {"rounds": n, "size": round(0.2 - 0.08 * d, 3), "speed": round(0.8 + 0.7 * d, 2), "need": 4 + round(d),
                "max_score": n, "seconds": n * 1.6}
    if game == G_PARRY:  # удар с одной из четырёх сторон — парировать туда же
        n = 14
        return {"strikes": n, "warn_ms": int(1000 - 450 * d), "need": 10 + round(2 * d), "max_score": n, "seconds": n * 1.2}
    if game == G_CHAIN:  # цели по одной, следующая сразу после попадания
        s = 10
        return {"seconds": s, "size": round(0.16 - 0.05 * d, 3), "need": 12 + round(8 * d), "max_score": s * 6}
    if game == G_HOLD:  # держи — шкала растёт, отпусти — падает; держать в зоне (счёт — десятые доли секунды)
        s = 12
        return {"seconds": s, "zone": round(0.25 - 0.1 * d, 3), "speed": round(0.6 + 0.6 * d, 2), "need": 60 + round(20 * d),
                "max_score": s * 10}
    if game == G_GONOGO:  # зелёный — бей, красный — нет
        n = 16
        return {"rounds": n, "window_ms": int(900 - 350 * d), "decoy": round(0.35 + 0.1 * d, 2), "need": 11 + round(2 * d),
                "max_score": n, "seconds": n * 1.1}
    if game == G_SPLIT:  # две точки разом — успеть обе
        n = 10
        return {"count": n, "life_ms": int(1500 - 600 * d), "need": 6 + round(2 * d), "max_score": n, "seconds": n * 1.4}
    raise KeyError(game)


# Мастерство: 4 игры вместо Тома Ли (+1 очко за каждую).
MASTERY_GAMES: dict[str, str] = {"strength": G_MASH, "speed": G_DOTS, "technique": G_COMBO, "endurance": G_DODGE}
# Сила: 20 с шквала, каждое нажатие бьёт долей мощи армии; нужно набить мощь Тома этапа.
MASTERY_STRENGTH_SECONDS = 20
MASTERY_POWER_PER_TAP = 1 / 40  # доля мощи армии за нажатие
MASTERY_TAPS_MIN, MASTERY_TAPS_MAX = 30, 110  # 1,5–5,5 нажатия в секунду (было до 7 — на телефоне почти предел)
# Выносливость: 20 ударов мощью Тома; каждый пропущенный снимает `MASTERY_HIT_SHARE` его мощи с армии.
MASTERY_STRIKES = 20
MASTERY_HIT_SHARE = 0.12
MASTERY_MISS_MIN, MASTERY_MISS_MAX = 4, 12  # хотя бы 4 пропуска допустимы (было 2 — при слабой армии почти без права на ошибку)
# Мастерство (жалоба 2026-11-24: «практически непроходимо», особенно стрелки комбо и уклонение): свои, более
# щадящие параметры — сложность этапа идёт вполсилы, а то, что показывается на экране, держится дольше.
MASTERY_DIFFICULTY_SHARE = 0.5


def mastery_params(game: str, d: float) -> dict:
    """Параметры игр «Преодоления стены» при сложности этапа `d` (0..1). Время показа — с запасом на
    «посмотреть и нажать» на телефоне."""
    d *= MASTERY_DIFFICULTY_SHARE
    if game == G_COMBO:  # стрелка серии горит 0,8–0,9 с, между стрелками 0,4 с; серия 3–4 удара
        length, show, gap = 3 + round(2 * d), int(900 - 200 * d), 400
        p = {"rounds": 3, "length": length, "show_ms": show, "gap_ms": gap, "need": 2, "max_score": 3,
             "seconds": 3 * (0.5 + length * (show + gap + 600) / 1000)}  # показ + ~0,6 с на ввод удара
    elif game == G_DOTS:  # точка живёт 1,4–1,6 с
        n = 14
        gap = 950 - 200 * d
        p = {"count": n, "life_ms": int(1600 - 400 * d), "gap_ms": int(gap), "need": math.ceil(n * (0.55 + 0.1 * d)),
             "max_score": n, "seconds": n * gap / 1000}
    elif game == G_DODGE:  # удар виден 1,1–1,3 с (было 0,55–0,95)
        n = MASTERY_STRIKES
        warn = int(1300 - 400 * d)
        p = {"strikes": n, "warn_ms": warn, "max_miss": MASTERY_MISS_MIN, "need": n - MASTERY_MISS_MIN, "max_score": n,
             "seconds": n * (warn + 300) / 1000}
    else:
        return params(game, d)
    p["min_seconds"] = round(_min_seconds(game, p), 2)
    return p

MIN_TIME_SHARE = 0.6  # быстрее этой доли длительности игру пройти нельзя (защита от подделки)
TOKEN_TTL_SECONDS = 15 * 60
