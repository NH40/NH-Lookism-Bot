"""Админка «Районы, города, императоры»: callback'и и значения статусов."""
from __future__ import annotations

P = "adm:w:"
CB_W_FIND = f"{P}find"
CB_W_CITY_PREFIX = f"{P}c:"  # + city_id
CB_W_DISTRICT_PREFIX = f"{P}d:"  # + district_id
CB_W_SET_OWNER_PREFIX = f"{P}so:"  # + district_id — ввод игрока
CB_W_RESET_ASK_PREFIX = f"{P}rs:"  # + district_id
CB_W_RESET_OK_PREFIX = f"{P}rsy:"
CB_W_SET_EMP_PREFIX = f"{P}se:"  # + city_id — ввод игрока
CB_W_DEL_EMP_ASK_PREFIX = f"{P}de:"
CB_W_DEL_EMP_OK_PREFIX = f"{P}dey:"
CB_W_CH_ASK_PREFIX = f"{P}cc:"  # + city_id — отменить вызовы на районы города
CB_W_CH_OK_PREFIX = f"{P}ccy:"
CB_W_WAR_ASK_PREFIX = f"{P}wr:"  # + city_id — отменить висящую войну императора города
CB_W_WAR_OK_PREFIX = f"{P}wry:"
CB_W_PICK_PREFIX = f"{P}pick:"  # + city_id из результатов поиска (то же, что CITY)

CHALLENGE_CANCELLED = "cancelled"
WAR_CANCELLED = "cancelled"
RESOLUTION_ADMIN = "admin"

AUDIT_W_SET_OWNER = "world_set_district_owner"
AUDIT_W_RESET = "world_reset_district"
AUDIT_W_SET_EMP = "world_set_emperor"
AUDIT_W_DEL_EMP = "world_remove_emperor"
AUDIT_W_CANCEL_CHALLENGES = "world_cancel_challenges"
AUDIT_W_CANCEL_WAR = "world_cancel_emperor_war"

SEARCH_LIMIT = 8
