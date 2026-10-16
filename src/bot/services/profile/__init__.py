"""Публичное API домена profile (сервис)."""
from bot.services.profile.profile import ProfileView, get_profile  # noqa: F401
from bot.services.profile.summary import DevItem, PhaseProgress, ProfileExtras, get_extras  # noqa: F401
