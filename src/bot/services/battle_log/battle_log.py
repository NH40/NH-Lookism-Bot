"""История боёв для разбора жалоб и баланса (2026-11-08). Пишется в транзакции самого боя, НЕ коммитит.

PvP, войны и бои за трон хранят подробности: раунды, шансы и бафы обеих сторон по источникам. Бои с ботами и
боссами — только итог, их намного больше."""
from __future__ import annotations

from dataclasses import fields

from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.ledger import DETAILED_BATTLES
from bot.db.models.battle_log import BattleLog
from bot.utils.log_context import current_source


def _nonzero(mods) -> dict:
    out = {}
    for f in fields(mods):
        value = getattr(mods, f.name)
        if value not in (0, 0.0, False):
            out[f.name] = round(value, 4) if isinstance(value, float) else value
    return out


def _side(chances) -> dict:
    return {
        "dodge": round(chances.dodge, 4), "block": round(chances.block, 4), "counter": round(chances.counter, 4), "flee": round(chances.flee, 4),
        "loss_save": round(chances.loss_save, 4), "absorb": round(chances.absorb, 4), "influence": chances.influence,
        "mods": _nonzero(chances.build.total),
        "sources": {name: _nonzero(mods) for name, mods in chances.build.by_source},
        "triggers": [t.name for t in chances.triggers],
    }


def _rounds(result) -> list[dict]:
    return [
        {
            "n": r.number, "a_dmg": r.attacker_damage, "d_dmg": r.defender_damage, "a_kills": r.attacker_kills, "d_kills": r.defender_kills,
            "a_chaos": r.attacker_chaos, "d_chaos": r.defender_chaos, "a_fired": list(r.attacker_fired), "d_fired": list(r.defender_fired),
        }
        for r in result.log
    ]


def record(session: AsyncSession, m, result, *, kind: str, attacker_id: int, defender_id: int | None, notes: tuple[str, ...] | list[str]) -> None:
    a, d = result.attacker, result.defender
    details = None
    if kind in DETAILED_BATTLES:
        details = {"rounds": _rounds(result), "attacker": _side(m.attacker), "defender": _side(m.defender)}
    session.add(BattleLog(
        kind=kind, attacker_id=attacker_id, defender_id=defender_id, attacker_won=result.attacker_won, rounds=result.rounds,
        a_quantity=a.initial_quantity, a_power=a.initial_power, a_dead=a.total_dead, a_fled=a.fled,
        d_quantity=d.initial_quantity, d_power=d.initial_power, d_dead=d.total_dead, d_fled=d.fled,
        notes="\n".join(notes)[:1000], details=details, source=current_source(),
    ))
