"""Админка «Кланы»: callback'и и ключи."""
from __future__ import annotations

P = "adm:c:"
CB_C_FIND = f"{P}find"
CB_C_VIEW_PREFIX = f"{P}v:"  # + clan_id
CB_C_TRANSFER_PREFIX = f"{P}tr:"  # + clan_id — список участников
CB_C_TRANSFER_PICK_PREFIX = f"{P}tp:"  # + clan_id:user_id — подтверждение
CB_C_TRANSFER_OK_PREFIX = f"{P}ty:"  # + clan_id:user_id
CB_C_LANDS_PREFIX = f"{P}ld:"  # + clan_id — ввод
CB_C_TREASURY_PREFIX = f"{P}tz:"  # + clan_id — ввод ±
CB_C_DONATE_PREFIX = f"{P}dl:"  # + clan_id — ввод
CB_C_SHIELD_PREFIX = f"{P}sh:"  # + clan_id — снять щит
CB_C_COOLDOWN_PREFIX = f"{P}cd:"  # + clan_id — снять КД войны
CB_C_DELETE_PREFIX = f"{P}dx:"  # + clan_id — подтверждение
CB_C_DELETE_OK_PREFIX = f"{P}dxy:"

FIELD_LANDS = "lands"
FIELD_TREASURY = "treasury"
FIELD_DONATE = "donate"
FSM_CLAN_ID = "clan_id"
FSM_FIELD = "field"

AUDIT_C_TRANSFER = "clan_transfer_owner"
AUDIT_C_LANDS = "clan_set_lands"
AUDIT_C_TREASURY = "clan_change_treasury"
AUDIT_C_DONATE = "clan_set_donate_level"
AUDIT_C_SHIELD = "clan_remove_shield"
AUDIT_C_COOLDOWN = "clan_remove_war_cooldown"
AUDIT_C_DELETE = "clan_delete"

SEARCH_LIMIT = 8
