"""Админка — роли, патч/вайп, настройки на лету (константы)."""
# Роли: adm:r:
CB_ROLES_LIST = "adm:r:list"
CB_ROLES_ADD = "adm:r:add"
CB_ROLES_USER_PREFIX = "adm:r:u:"  # + user_id
CB_ROLES_SET_PREFIX = "adm:r:set:"  # + user_id:role
CB_ROLES_DEL_ASK_PREFIX = "adm:r:da:"  # + user_id
CB_ROLES_DEL_PREFIX = "adm:r:del:"  # + user_id

# Патч и вайп: adm:pt:
CB_PATCH_PATCH_INFO = "adm:pt:pi"
CB_PATCH_PATCH_STEP1 = "adm:pt:p1"
CB_PATCH_PATCH_STEP2 = "adm:pt:p2"
CB_PATCH_WIPE_INFO = "adm:pt:wi"
CB_PATCH_WIPE_STEP1 = "adm:pt:w1"
CB_PATCH_WIPE_STEP2 = "adm:pt:w2"
CONFIRM_TTL_SECONDS = 30
PATCH_BATCH_SIZE = 200
PATCH_RUNNING_TTL_SECONDS = 6 * 3600  # страховка: упавший процесс не держит флаг вечно
WIPE_KEEP_TABLES = ("lbp1_donations",)  # перенос доната из 1.3 не теряем
CONFIRM_KIND_PATCH = "patch"
CONFIRM_KIND_WIPE = "wipe"

# Настройки на лету: adm:cf:
CB_CONFIG_LIST = "adm:cf:list"
CB_CONFIG_KEY_PREFIX = "adm:cf:k:"  # + key
CB_CONFIG_SET_PREFIX = "adm:cf:s:"  # + key
CB_CONFIG_DUR_PREFIX = "adm:cf:d:"  # + key:hours (0 — навсегда)
CB_CONFIG_RESET_PREFIX = "adm:cf:r:"  # + key

# Аудит
AUDIT_ROLE_SET = "role_set"
AUDIT_ROLE_REMOVE = "role_remove"
AUDIT_PATCH = "patch_all"
AUDIT_WIPE = "wipe_db"
AUDIT_CONFIG_SET = "cfg_set"
AUDIT_CONFIG_RESET = "cfg_reset"

# Ключи настроек
KEY_BP_XP_MULT = "bp_xp_multiplier"
KEY_INCOME_MULT = "income_multiplier"
KEY_START_COINS = "starting_nh_coins"
KEY_START_TICKETS = "starting_tickets"
KEY_BP_PRICE = "bp_premium_price"
KEY_BODY_PRICE = "second_body_price"

CONFIG_DURATIONS = ((1, "1ч"), (24, "24ч"), (72, "3д"), (168, "7д"), (0, "Навсегда"))
