"""Админка: действия над игроком из карточки (выдача, развитие, наказания) — константы.

Префиксы `callback_data` начинаются с `adm:g:` / `adm:d:` / `adm:x:`; хвост — `...:{user_id}`
всегда последним полем (его читает `parse_id`)."""
from __future__ import annotations

# --- Выдать/забрать (adm:g:) ---
CB_GIVE_MENU = "adm:g:m:"  # + uid
CB_GIVE_RES_LIST = "adm:g:r:"  # + uid — список ресурсов
CB_GIVE_RES_PICK = "adm:g:rs:"  # + code:uid
CB_GIVE_STATIST = "adm:g:st:"  # + uid
CB_GIVE_CARD = "adm:g:cd:"  # + uid
CB_GIVE_SCROLLS = "adm:g:sk:"  # + uid
CB_GIVE_XP = "adm:g:xp:"  # + uid

GIVE_KIND_RESOURCE = "res"
GIVE_KIND_STATIST = "statist"
GIVE_KIND_CARD = "card"
GIVE_KIND_SCROLLS = "scrolls"
GIVE_KIND_XP = "xp"

# --- Развитие (adm:d:) ---
CB_DEV_MENU = "adm:d:m:"  # + uid
CB_DEV_LIST = "adm:d:l:"  # + kind:uid
CB_DEV_ITEM = "adm:d:i:"  # + kind:idx:uid
CB_DEV_LEVEL = "adm:d:s:"  # + kind:idx:level:uid (level 0 — забрать)
CB_DEV_ACTIVE = "adm:d:a:"  # + kind:idx:uid
CB_DEV_BLOOD = "adm:d:b:"  # + slot:uid — экран родословной
CB_DEV_BLOOD_PICK = "adm:d:bc:"  # + slot:idx:uid (idx = BLOOD_NONE — убрать)
CB_DEV_BLOOD_LEVEL = "adm:d:bl:"  # + slot:level:uid
CB_DEV_MISC = "adm:d:o:"  # + uid
CB_DEV_BODY = "adm:d:tb:"  # + uid — второе тело
CB_DEV_PASS = "adm:d:tp:"  # + uid — премиум Battle Pass
CB_DEV_AWAKEN = "adm:d:aw:"  # + level:uid
CB_DEV_POTENTIAL = "adm:d:po:"  # + idx:uid
CB_DEV_STATS = "adm:d:st:"  # + uid — выбор характеристики
CB_DEV_STAT_PICK = "adm:d:sr:"  # + stat:uid

DEV_KIND_PATH = "path"
DEV_KIND_TECH = "tech"
DEV_KIND_GENIUS = "gen"
DEV_KINDS = (DEV_KIND_PATH, DEV_KIND_TECH, DEV_KIND_GENIUS)
BLOOD_NONE = 99
BLOOD_SLOTS = (1, 2)

# --- Наказания (adm:x:) ---
CB_PUNISH_MENU = "adm:x:m:"  # + uid
CB_PUNISH_BAN = "adm:x:b:"  # + uid — выбор срока
CB_PUNISH_BAN_DURATION = "adm:x:bd:"  # + key:uid
CB_PUNISH_BAN_NO_REASON = "adm:x:bn:"  # + key:uid
CB_PUNISH_UNBAN = "adm:x:ub:"  # + uid
CB_PUNISH_COOLDOWNS = "adm:x:cd:"  # + uid
CB_PUNISH_RESET_ASK = "adm:x:rs:"  # + uid
CB_PUNISH_RESET_YES = "adm:x:rsy:"  # + uid
CB_PUNISH_DELETE_ASK = "adm:x:dl:"  # + uid
CB_PUNISH_DELETE_YES = "adm:x:dly:"  # + uid

# Срок бана: ключ → секунды (None — навсегда).
BAN_DURATIONS: dict[str, int | None] = {
    "1h": 3600, "1d": 86400, "7d": 7 * 86400, "30d": 30 * 86400, "forever": None,
}
BAN_REASON_MAX_LEN = 256

# Шаблоны ключей Redis с кулдаунами/щитами игрока (см. `cache/keys.py`).
COOLDOWN_KEY_PATTERNS: tuple[str, ...] = ("cooldown:*:{uid}", "shield:*:{uid}")

# Действия аудита.
AUDIT_GIVE_RESOURCE = "give_resource"
AUDIT_GIVE_STATIST = "give_statist"
AUDIT_GIVE_CARD = "give_card"
AUDIT_GIVE_SCROLLS = "give_scrolls"
AUDIT_GIVE_BP_XP = "give_bp_xp"
AUDIT_DEV_SET_LEVEL = "dev_set_level"
AUDIT_DEV_SET_ACTIVE = "dev_set_active"
AUDIT_DEV_BLOODLINE = "dev_bloodline"
AUDIT_DEV_BODY = "dev_second_body"
AUDIT_DEV_PASS = "dev_premium_pass"
AUDIT_DEV_AWAKENING = "dev_awakening"
AUDIT_DEV_POTENTIAL = "dev_potential"
AUDIT_DEV_STAT = "dev_stat_rank"
AUDIT_BAN = "ban"
AUDIT_UNBAN = "unban"
AUDIT_RESET_PLAYER = "reset_player"
AUDIT_DELETE_ACCOUNT = "delete_account"
AUDIT_CLEAR_COOLDOWNS = "clear_cooldowns"

# Статисты игрока кнопками (2026-10-13: «более лёгкая выдача и возможность забрать статистов»).
CB_AST_MENU = "adm:km:"  # + uid
CB_AST_SQUAD = "adm:kq:"  # + key:uid (StatistKey.encode)
CB_AST_TAKE = "adm:kt:"  # + pct:key:uid
CB_AST_ADD = "adm:ka:"  # + n:key:uid
CB_AST_RANKS = "adm:kr:"  # + page:uid
CB_AST_GIVE = "adm:kg:"  # + rank:n:uid (n=0 — выбор количества)
CB_AST_WIPE_ASK = "adm:kw:"  # + uid
CB_AST_WIPE = "adm:kwy:"  # + uid
# Фаза игрока (2026-10-13: «быстро перекидывать игроков по стадиям»).
CB_ADMIN_PHASE = "adm:kp:"  # + phase:uid
AST_TAKE_PERCENTS: tuple[int, ...] = (10, 50, 100)
AST_ADD_AMOUNTS: tuple[int, ...] = (100, 1_000, 10_000)
AST_GIVE_AMOUNTS: tuple[int, ...] = (100, 1_000, 10_000, 100_000, 1_000_000)
AST_RANKS_PER_PAGE = 15
AUDIT_PHASE = "set_phase"
AUDIT_WIPE_STATISTS = "wipe_statists"
