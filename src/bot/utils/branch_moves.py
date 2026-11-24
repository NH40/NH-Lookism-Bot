"""Приёмы ветки (родословной или пути) для экранов развития — бот и Mini App (v3, 2026-11-24).

Открытый приём показывается с силой на текущем уровне ветки, закрытый — с силой на уровне, где он откроется.
"""
from __future__ import annotations

from dataclasses import dataclass

from bot.utils.formatting import esc


@dataclass(frozen=True, slots=True)
class MoveRow:
    name: str
    about: str
    unlocked: bool
    unlock_level: int
    cost: int
    cooldown: int
    minigame: bool


def branch_move_rows(kind: str, code: str | None, level: int) -> list[MoveRow]:
    from bot.config.arena.branches import BRANCH_MAX_LEVEL, BRANCH_UNLOCK, branch_moves
    from bot.services.arena.arena import PERK_REGISTRY

    if not code:
        return []
    out = []
    for n, _ in enumerate(branch_moves(kind, code), 1):
        unlock = BRANCH_UNLOCK[n - 1]
        shown = min(BRANCH_MAX_LEVEL, max(level, unlock))
        p = PERK_REGISTRY.get(f"{kind}:{code}:{n}@{shown}")
        if p is None:
            continue
        out.append(MoveRow(p.name, p.about, level >= unlock, unlock, p.cost, p.cooldown, bool(p.minigame)))
    return out


def branch_moves_block(kind: str, code: str | None, level: int) -> str:
    rows = branch_move_rows(kind, code, level)
    if not rows:
        return ""
    lines = ["\n\n⚔️ <b>Приёмы в бою</b> <i>(сила растёт с уровнем)</i>"]
    for r in rows:
        mark = "✦" if r.unlocked else f"🔒 с {r.unlock_level} ур. ·"
        lines.append(f"{mark} <b>{esc(r.name)}</b> · ⚡{r.cost}\n   <i>{esc(r.about)}</i>")
    return "\n".join(lines)
