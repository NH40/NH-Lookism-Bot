"""Журнал боя — подписи разбора раунда (2026-11-23). Строки собирает `services/combat/explain`."""
from __future__ import annotations

__all__ = [
    "SOURCE_LABELS", "PART_LABELS", "POWER_DECISIVE", "POWER_EDGE_ME", "POWER_EDGE_FOE", "POWER_EVEN",
    "STRIKE_BASE", "STRIKE_ACTION", "STRIKE_PART", "STRIKE_ATTACK", "STRIKE_CRIT", "STRIKE_CRIT_CUT", "STRIKE_HELD", "STRIKE_CHAOS",
    "STRIKE_TOTAL", "IN_WARD", "IN_STORED", "IN_REDUCTION", "IN_PIERCE", "IN_SURE", "IN_REACTIONS", "IN_HP",
    "IN_REACHED", "IN_COUNTER", "HEALED", "SHORT_LINE", "UNITS",
]

SOURCE_LABELS = {
    "path": "путь", "path2": "путь второго тела", "technique": "техника", "bloodline": "родословная",
    "bloodline2": "вторая родословная", "genius": "гениальность", "mastery": "техники мастерства", "triggers": "навыки позиций",
    "action": "действие раунда", "enemy": "ослабление от противника", "other": "прочее: характеристики, зелья, пробуждение, мастерство, копирование",
}
PART_LABELS = {
    "cleave": "удар по нескольким целям", "gap": "Преодоление: закрывает разрыв в мощи",
    "dominance": "Отчаяние: давит более слабого", "influence": "влияние", "endure": "терпение: растёт с каждым раундом",
    "vs_stronger": "против более сильного", "absorb_power": "поглощённый урон бьёт обратно",
    "dodge_surge": "сила от уклонений", "overcome": "Преодоление: от полученного урона", "despair": "Отчаяние: шкала",
    "adapt": "адаптация после потерь", "rush": "натиск первых раундов", "ramp": "разгон по раундам",
    "opening": "сильный первый раунд", "grow_on_kill": "рост от убитых", "cqc": "стаки CQC",
    "broken": "стаки сбиты Сейримом противника",
}
POWER_DECISIVE = "⚖️ Перевес мощи ×{ratio} — бой решает мощь: {who} побеждает, прокачка слабого не работает."
POWER_EDGE_ME = "⚖️ Твоя мощь больше в ×{ratio} — прокачка противника работает на {weight}%."
POWER_EDGE_FOE = "⚖️ Мощь противника больше в ×{ratio} — твоя прокачка работает на {weight}%."
POWER_EVEN = "⚖️ Мощь почти равна — прокачка обеих сторон работает полностью."

STRIKE_BASE = "Базовый урон: мощь {power} × 30% × разброс {var} = {base}"
STRIKE_ACTION = "  ×{mult} {name}"
STRIKE_ATTACK = "  {sign}{value}% атака: {sources}"
STRIKE_PART = "  {sign}{value}% {label}"
STRIKE_CRIT = "  ×{mult} крит"
STRIKE_CRIT_CUT = "  ×{mult} крит срезан противником"
STRIKE_HELD = "  −{value}% захват Сейрима: часть армии не бьёт"
STRIKE_CHAOS = "  ×2 хаос!"
STRIKE_TOTAL = "  = {total} урона"
IN_WARD = "  🛡 первый удар погашен щитом"
IN_STORED = "  🧲 поглощено в запас: {value}"
IN_REDUCTION = "  −{value}% гашение: {parts}"
IN_PIERCE = "  (пробитие {value}% брони)"
IN_SURE = "  {value} прошло наверняка, мимо уклонений и блоков"
IN_REACTIONS = "  реакции: ушли {fled}, уклонились {dodged}, блок {blocked}, контратака {countered}"
IN_HP = "  прочность бойцов ×{mult}"
IN_REACHED = "  → дошло {reached}, погибло {deaths} {units}"
IN_COUNTER = "  ↩ контратаки в ответ: {value}"
HEALED = "💚 Лечение {pct}%: встали {count}"
SHORT_LINE = "Р{n} · {me_act} {me_hit} → −{me_kills} · он {foe_act} {foe_hit} → −{foe_kills}"
UNITS = "бойцов"
