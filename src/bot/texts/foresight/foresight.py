"""Предвидение — строка прогноза боя (тексты)."""
from __future__ import annotations


def forecast_line(forecast) -> str:
    """Строка прогноза для экрана перед боем; точность — по уровню предвидения."""
    if forecast is None:
        return ""
    if forecast.level >= 3:
        chance = f"{forecast.win_rate * 100:.0f}%"
    else:
        chance = f"≈{round(forecast.win_rate * 10) * 10}%"
    line = f"\n\n🔮 <b>Предвидение:</b> шанс победы {chance}"
    if forecast.level >= 2:
        line += f", потери ≈{forecast.loss_share * 100:.0f}% армии"
    return line
