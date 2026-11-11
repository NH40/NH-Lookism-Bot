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

# Объявления императора.
CB_EMPIRE_ANNOUNCE = "empire:announce"
CB_EMPIRE_ANNOUNCE_WRITE = "empire:announce:write"
CB_EMPIRE_ANNOUNCE_SEND = "empire:announce:send"
CB_EMPIRE_LOG_PREFIX = "empire:log:"
"""f"{CB_EMPIRE_LOG_PREFIX}{page}" — журнал объявлений у игрока."""

# Сложить империю (`services/empire/abdicate`).
CB_EMPIRE_ABDICATE = "empire:abd"
CB_EMPIRE_ABDICATE_TO_PREFIX = "empire:abd:to:"  # + код страны — подтверждение
CB_EMPIRE_ABDICATE_YES_PREFIX = "empire:abd:yes:"  # + код страны — выполнить

# --- Ивенты императора (`empire_events.kind` / `status`) ---
EVENT_COINS = "coins"  # раздача NHCoin
EVENT_STATISTS = "statists"  # раздача статистов
EVENT_FEAST = "feast"  # праздник: +% дохода подданным из фонда
EVENT_HOLIDAY = "holiday"  # налоговые каникулы
EVENT_DRILL = "drill"  # военные сборы: −% КД тренировок
EVENT_TOURNAMENT = "tournament"  # турнир по победам в PvP
EVENT_DAILY = "daily"  # ежедневный подарок NHCoin
EVENT_KINDS: tuple[str, ...] = (EVENT_COINS, EVENT_STATISTS, EVENT_FEAST, EVENT_HOLIDAY, EVENT_DRILL, EVENT_TOURNAMENT, EVENT_DAILY)
EVENT_ACTIVE = "active"
EVENT_DONE = "done"
LOCK_ACTION_EMPIRE_EVENT = "empire_event"

CB_EVENTS_OPEN = "emev:open"  # император — список видов
CB_EVENTS_KIND_PREFIX = "emev:k:"  # + kind — экран вида
CB_EVENTS_HOURS_PREFIX = "emev:h:"  # + kind:hours — длительность (праздник/каникулы/сборы)
CB_EVENTS_START_PREFIX = "emev:go:"  # + kind:hours — подтвердить запуск (каникулы/сборы)
CB_EVENTS_SUBJECT = "emev:sub"  # подданный — ивенты его империи
CB_EVENTS_CLAIM_PREFIX = "emev:c:"  # + event_id — забрать

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
