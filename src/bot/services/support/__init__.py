"""Публичное API домена support (сервис)."""
from bot.services.support.support import *  # noqa: F401,F403
from bot.services.support.support import ANSWERED, CLOSED, MAX_TEXT, OPEN, SupportError, close, my_thread, queue, reply, thread, write  # noqa: F401
