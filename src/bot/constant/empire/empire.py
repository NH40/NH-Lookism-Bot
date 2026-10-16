"""Император — экран «👑 Империя», налоги (константы)."""
from __future__ import annotations

CB_EMPIRE_OPEN = "empire:open"
CB_EMPIRE_RATE_PREFIX = "empire:rate:"
"""f"{CB_EMPIRE_RATE_PREFIX}{percent}" — общая ставка налога."""
CB_EMPIRE_PERSONAL = "empire:personal"
"""Персональная ставка — спросить юзернейм игрока."""
CB_EMPIRE_PERSONAL_RATE_PREFIX = "empire:prate:"
"""f"{CB_EMPIRE_PERSONAL_RATE_PREFIX}{user_id}:{percent|EMPIRE_RATE_RESET}"."""
EMPIRE_RATE_RESET = "reset"

# Саботаж снизу — вид действия (ключ шансов в `config/empire`, `sabotage_logs.action`).
SABOTAGE_STATISTS = "statists"
SABOTAGE_UNIQUE = "unique"
SABOTAGE_TREASURY = "treasury"
SABOTAGE_ACTIONS: tuple[str, ...] = (SABOTAGE_STATISTS, SABOTAGE_UNIQUE, SABOTAGE_TREASURY)

CB_SABOTAGE_OPEN = "sabotage:open"
CB_SABOTAGE_DO_PREFIX = "sabotage:do:"
CB_SABOTAGE_MARKED_PREFIX = "sabotage:mk:"
"""f"{CB_SABOTAGE_MARKED_PREFIX}{action}:{target_id}" — саботаж помеченного (путь Сенсорики)."""
"""f"{CB_SABOTAGE_DO_PREFIX}{action}"."""

# --- Война императоров ---
WAR_PENDING = "pending"
WAR_RESOLVED = "resolved"
WAR_ACCEPTED = "accepted"  # защитник принял — бой
WAR_FORFEIT = "forfeit"  # не принял до срока — проиграл без боя
WAR_VOID = "void"  # к моменту боя кто-то уже не император / у защитника нет городов

CB_WAR_LIST_PREFIX = "war:list:"
"""f"{CB_WAR_LIST_PREFIX}{page}" — список императоров-целей."""
CB_WAR_TARGET_PREFIX = "war:target:"
"""f"{CB_WAR_TARGET_PREFIX}{user_id}" — экран цели перед объявлением."""
CB_WAR_DECLARE_PREFIX = "war:declare:"
"""f"{CB_WAR_DECLARE_PREFIX}{user_id}"."""
CB_WAR_ACCEPT_PREFIX = "war:accept:"
"""f"{CB_WAR_ACCEPT_PREFIX}{war_id}" — защитник принимает бой."""
