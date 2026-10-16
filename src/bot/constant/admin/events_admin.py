"""Админка «События карты»: callback'и и ключи."""
from __future__ import annotations

P = "adm:e:"
CB_E_LIST = f"{P}list"
CB_E_VIEW_PREFIX = f"{P}v:"  # + event_id
CB_E_RM_ASK_PREFIX = f"{P}rm:"
CB_E_RM_OK_PREFIX = f"{P}rmy:"
CB_E_SPAWN = f"{P}sp"
CB_E_KIND_PREFIX = f"{P}sk:"  # + kind_key
CB_E_CODE_PREFIX = f"{P}sc:"  # + kind_key:code_idx — экран выбора пушей
CB_E_GO_PREFIX = f"{P}go:"  # + kind_key:code_idx:push(0/1)

# Короткие ключи видов (callback_data ≤ 64 байт).
KIND_BOSS_KEY = "b"
KIND_TEACHER_KEY = "t"
KIND_SCHOOL_KEY = "s"

AUDIT_E_REMOVE = "event_remove"
AUDIT_E_SPAWN = "event_spawn"
