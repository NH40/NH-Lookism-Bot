"""Публичное API домена recruit (сервис)."""
from bot.services.recruit.recruit import (  # noqa: F401
    PHASE_RANK_CAP_INDEX,
    RecruitOnCooldownError,
    RecruitResult,
    get_influence,
    recruit_extra,
    roll_extra_rank,
)
