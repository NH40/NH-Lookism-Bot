"""Публичное API домена resource (сервис)."""
from bot.services.resource.resource import UnknownResourceError, balance, balances, grant, spend  # noqa: F401
from bot.services.resource.statists import StatistKey, give_statists, take_statists  # noqa: F401
from bot.services.resource.items import InvalidItemError, check_item, give_item, take_item  # noqa: F401
