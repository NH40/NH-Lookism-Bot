"""Журнал боя по-человечески (2026-11-23): из разбора раунда (`RoundLog.*_detail`) — строки «откуда что и почему».

Одна точка для бота и Mini App: API отдаёт готовые строки, формулировки не разъезжаются.
"""
from __future__ import annotations

from bot.texts.battle import (
    HEALED, IN_COUNTER, IN_HP, IN_PIERCE, IN_REACHED, IN_REACTIONS, IN_REDUCTION, IN_STORED, IN_SURE, IN_WARD,
    PART_LABELS, POWER_DECISIVE, POWER_EDGE_FOE, POWER_EDGE_ME, POWER_EVEN, SHORT_LINE, SOURCE_LABELS, STRIKE_ACTION,
    STRIKE_ATTACK, STRIKE_BASE, STRIKE_CHAOS, STRIKE_CRIT, STRIKE_CRIT_CUT, STRIKE_HELD, STRIKE_PART, STRIKE_TOTAL, UNITS,
)
from bot.config.game import BATTLE_DAMAGE_FRACTION, BATTLE_POWER_DECISIVE_RATIO


def compact(value: float) -> str:
    """1 240 000 000 → «1,24 млрд», 402 000 000 → «402 млн», 75 300 → «75,3 тыс.»."""
    v = abs(value)
    for size, unit in ((1e12, "трлн"), (1e9, "млрд"), (1e6, "млн"), (1e4, "тыс.")):
        if v >= size:
            x = value / size
            digits = 0 if abs(x) >= 100 else 1 if abs(x) >= 10 else 2
            return f"{x:.{digits}f}".rstrip("0").rstrip(".").replace(".", ",") + f" {unit}"
    return f"{int(round(value)):,}".replace(",", " ")


def _pct(v: float) -> str:
    x = abs(v) * 100
    return (f"{x:.0f}" if x >= 10 else f"{x:.1f}".rstrip("0").rstrip(".")).replace(".", ",")


def _mult(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def power_line(ratio: float, me_stronger: bool, weak_weight: float) -> str:
    r = f"{ratio:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    if ratio >= BATTLE_POWER_DECISIVE_RATIO:
        return POWER_DECISIVE.format(ratio=r, who="ты" if me_stronger else "противник")
    if ratio < 1.05:
        return POWER_EVEN
    tpl = POWER_EDGE_ME if me_stronger else POWER_EDGE_FOE
    return tpl.format(ratio=r, weight=round(weak_weight * 100))


def strike(out: dict, foe_in: dict, action: str) -> list[str]:
    """Удар стороны: из чего сложился её урон (`out`) и что с ним сделала защита противника (`foe_in`)."""
    if not out:
        return []
    lines = [STRIKE_BASE.format(power=compact(out["power"]), var=_mult(out["var"]),
                                base=compact(out["power"] * BATTLE_DAMAGE_FRACTION * out["var"]))]
    if out.get("act", 1.0) != 1.0:
        lines.append(STRIKE_ACTION.format(mult=_mult(out["act"]), name=action))
    for code, v in out.get("parts", []):
        if abs(v) < 0.0005:
            continue
        sign = "+" if v > 0 else "−"
        if code == "attack":
            src = ", ".join(f"{SOURCE_LABELS.get(k, k)} {'+' if x > 0 else '−'}{_pct(x)}%" for k, x in out.get("src", []) if abs(x) >= 0.0005)
            lines.append(STRIKE_ATTACK.format(sign=sign, value=_pct(v), sources=src or SOURCE_LABELS["other"]))
        else:
            lines.append(STRIKE_PART.format(sign=sign, value=_pct(v), label=PART_LABELS.get(code, code)))
    if abs(out.get("crit", 1.0) - 1) >= 0.005:
        lines.append((STRIKE_CRIT if out["crit"] > 1 else STRIKE_CRIT_CUT).format(mult=_mult(out["crit"])))
    if out.get("held"):
        lines.append(STRIKE_HELD.format(value=_pct(out["held"])))
    if out.get("chaos"):
        lines.append(STRIKE_CHAOS)
    lines.append(STRIKE_TOTAL.format(total=compact(out.get("total", 0))))
    if not foe_in:
        return lines
    if foe_in.get("ward"):
        lines.append(IN_WARD)
    if foe_in.get("stored"):
        lines.append(IN_STORED.format(value=compact(foe_in["stored"])))
    if foe_in.get("reduction"):
        parts = [f"{name} {_pct(v)}%" for name, v in (("поглощение", foe_in.get("absorb", 0)), ("броня", foe_in.get("armor", 0)),
                                                       ("стойкость по раундам", foe_in.get("guard", 0))) if v]
        lines.append(IN_REDUCTION.format(value=_pct(foe_in["reduction"]), parts=", ".join(parts)))
    if foe_in.get("pierce"):
        lines.append(IN_PIERCE.format(value=_pct(foe_in["pierce"])))
    if foe_in.get("sure"):
        lines.append(IN_SURE.format(value=compact(foe_in["sure"])))
    return lines


def defence_tail(foe: dict) -> list[str]:
    """Чем кончился удар по противнику: реакции, прочность, погибшие, контратаки (`foe` — разбор противника)."""
    fin = foe.get("in") or {}
    if not fin:
        return []
    lines = []
    fled, dodged, blocked, countered = foe.get("rx", [0, 0, 0, 0])
    if fled or dodged or blocked or countered:
        lines.append(IN_REACTIONS.format(fled=compact(fled), dodged=compact(dodged), blocked=compact(blocked), countered=compact(countered)))
    if fin.get("hp", 1.0) > 1.005:
        lines.append(IN_HP.format(mult=_mult(fin["hp"])))
    lines.append(IN_REACHED.format(reached=compact(fin.get("reached", 0)), deaths=compact(fin.get("deaths", 0)), units=UNITS))
    if fin.get("counter"):
        lines.append(IN_COUNTER.format(value=compact(fin["counter"])))
    return lines


def side_lines(me: dict, foe: dict, action: str) -> list[str]:
    """Полный разбор хода стороны `me` в раунде: удар → защита противника → итог → своё лечение."""
    lines = strike(me.get("out") or {}, foe.get("in") or {}, action) + defence_tail(foe)
    if me.get("healed"):
        lines.append(HEALED.format(pct=_pct(me.get("heal", 0)), count=compact(me["healed"])))
    return lines


def short_line(n: int, me_act: str, foe_act: str, me_hit: float, foe_hit: float, me_kills: int, foe_kills: int) -> str:
    return SHORT_LINE.format(n=n, me_act=me_act, foe_act=foe_act, me_hit=compact(me_hit), foe_hit=compact(foe_hit),
                             me_kills=compact(me_kills), foe_kills=compact(foe_kills))
