"""Админка «Сезон пасса и задания»: callback'и и ключи."""
from __future__ import annotations

P = "adm:se:"
CB_SE_NEW_ASK = f"{P}ns"
CB_SE_NEW_OK = f"{P}nsy"
CB_SE_PLAYER = f"{P}pl"  # ввод игрока
CB_SE_CARD_PREFIX = f"{P}p:"  # + user_id
CB_SE_XP_PREFIX = f"{P}xp:"  # + user_id — ввод
CB_SE_PREMIUM_PREFIX = f"{P}pr:"  # + user_id
CB_SE_RESET_ASK_PREFIX = f"{P}rc:"
CB_SE_RESET_OK_PREFIX = f"{P}rcy:"
CB_SE_QUESTS_PREFIX = f"{P}q:"  # + user_id
CB_SE_QUEST_DONE_PREFIX = f"{P}qc:"  # + user_id:slot
CB_SE_QUEST_REROLL_ASK_PREFIX = f"{P}qr:"
CB_SE_QUEST_REROLL_OK_PREFIX = f"{P}qry:"

FSM_USER_ID = "user_id"

AUDIT_SE_NEW_SEASON = "season_new"
AUDIT_SE_XP = "season_give_xp"
AUDIT_SE_PREMIUM = "season_toggle_premium"
AUDIT_SE_RESET_CLAIMS = "season_reset_claims"
AUDIT_SE_QUEST_DONE = "quest_complete"
AUDIT_SE_QUEST_REROLL = "quest_reroll_set"

XP_LIMIT = 10_000_000
