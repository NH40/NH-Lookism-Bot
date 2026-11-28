"""Публичное API домена training (сервис)."""
from bot.services.training.personal import PersonalTrainResult, personal_cooldown_left, train_personal  # noqa: F401
from bot.services.training.training import (  # noqa: F401
    NothingToPromoteError,
    RankControlRow,
    RankHoldUnavailableError,
    TrainingOnCooldownError,
    TrainResult,
    promote_rank,
    rank_control,
    toggle_rank_lock,
    train_extras,
)
from bot.services.training.focus import (  # noqa: F401
    FocusRow,
    FocusSlotsFullError,
    FocusUnavailableError,
    FocusView,
    focus_view,
    toggle_focus,
)
