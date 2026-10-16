"""Реферальные кампании (константы)."""
from __future__ import annotations

REF_START_PREFIX = "ref_"  # /start ref_<code>
REF_CODE_BYTES = 4  # secrets.token_hex → 8 символов
REF_NAME_MAX_LEN = 64
REF_ACTIVE_DAYS = 7  # «ещё играет» = активность за 7 суток
REF_LIST_LIMIT = 30
