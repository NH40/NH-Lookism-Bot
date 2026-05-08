from datetime import datetime, timezone, timedelta
from app.models.user import User

TRUCE_DURATION_HOURS = 10
TRUCE_COOLDOWN_HOURS = 12


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_truce_active(user: User) -> bool:
    if not user.truce_until:
        return False
    return _aware(user.truce_until) > datetime.now(timezone.utc)


def truce_remaining_secs(user: User) -> int:
    if not user.truce_until:
        return 0
    delta = _aware(user.truce_until) - datetime.now(timezone.utc)
    return max(0, int(delta.total_seconds()))


def is_truce_on_cooldown(user: User) -> bool:
    if is_truce_active(user):
        return False
    if not user.truce_cd_until:
        return False
    return _aware(user.truce_cd_until) > datetime.now(timezone.utc)


def truce_cd_remaining_secs(user: User) -> int:
    if not user.truce_cd_until:
        return 0
    delta = _aware(user.truce_cd_until) - datetime.now(timezone.utc)
    return max(0, int(delta.total_seconds()))


def truce_button_label(user: User) -> str:
    from app.utils.formatters import fmt_ttl
    if is_truce_active(user):
        return f"🕊 Перемирие [{fmt_ttl(truce_remaining_secs(user))}]"
    if is_truce_on_cooldown(user):
        return f"⏳ Перемирие КД [{fmt_ttl(truce_cd_remaining_secs(user))}]"
    return "🕊 Перемирие"
