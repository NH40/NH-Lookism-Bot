"""Админка/рассылка и массовая выдача: фильтры аудитории и callback_data (префикс adm:m:)."""
from __future__ import annotations

FLT_ALL = "all"
FLT_ACTIVE_24H = "a24"
FLT_ACTIVE_7D = "a7"
FLT_DONORS = "don"
FLT_CLAN = "clan"
FLT_NO_ROLE = "norole"  # игроки без админ-роли
FILTERS: tuple[str, ...] = (FLT_ALL, FLT_ACTIVE_24H, FLT_ACTIVE_7D, FLT_DONORS, FLT_CLAN, FLT_NO_ROLE)

CB_MASS_BROADCAST = "adm:m:bc"
CB_MASS_GRANT = "adm:m:gr"
CB_MASS_FILTER_PREFIX = "adm:m:f:"
CB_MASS_RES_PREFIX = "adm:m:r:"
CB_MASS_SKIP_BUTTON = "adm:m:skip"
CB_MASS_BROADCAST_GO = "adm:m:bgo"
CB_MASS_GRANT_GO = "adm:m:ggo"

# Ключи FSM-данных.
KEY_MODE = "mass_mode"
KEY_FILTER = "mass_filter"
KEY_CLAN_ID = "mass_clan_id"
KEY_CLAN_NAME = "mass_clan_name"
KEY_CONTENT = "mass_content"
KEY_RESOURCE = "mass_resource"
KEY_AMOUNT = "mass_amount"
MODE_BROADCAST = "bc"
MODE_GRANT = "gr"

BROADCAST_BATCH_SIZE = 25
BROADCAST_BATCH_PAUSE_SECONDS = 1.0
BROADCAST_TEXT_LIMIT = 4096
BROADCAST_CAPTION_LIMIT = 1024
MASS_GRANT_MAX_AMOUNT = 1_000_000_000

ACTIVE_24H_HOURS = 24
ACTIVE_7D_HOURS = 24 * 7
