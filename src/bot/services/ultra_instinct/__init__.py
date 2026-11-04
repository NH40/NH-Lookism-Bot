"""Публичное API домена ultra_instinct (сервис)."""
from bot.services.ultra_instinct.ultra_instinct import (  # noqa: F401
    ULTRA_INSTINCT_TICK_SECONDS,
    ULTRA_LOSS_OPTIONS,
    AutomationReport,
    MaxLossError,
    UltraUnavailableError,
    UltraView,
    get_view,
    run_once,
    set_max_loss,
    toggle_action,
    toggle_boss,
)
