"""Публичное API домена absolute (сервис)."""
from bot.services.absolute.absolute import StylistError, active, owned, set_style_pick, style_pick  # noqa: F401
from bot.services.absolute.battle import after_battle  # noqa: F401,E402
from bot.services.absolute.arkhangel import ARKHANGEL_SWEEP_SECONDS, sweep as arkhangel_sweep  # noqa: F401,E402
