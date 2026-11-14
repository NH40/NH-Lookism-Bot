"""Банки игроков и кредиты (константы)."""
from __future__ import annotations

CB_BANK_OPEN = "bank:open"  # список банков
CB_BANK_PAGE_PREFIX = "bank:page:"  # f"{...}{page}"
CB_BANK_VIEW_PREFIX = "bank:view:"  # f"{...}{bank_id}" — карточка банка
CB_BANK_TAKE_PREFIX = "bank:take:"  # f"{...}{bank_id}" — взять кредит (ввод суммы)
CB_BANK_DAYS_PREFIX = "bank:days:"  # f"{...}{days}" — срок в мастере кредита
CB_BANK_CONFIRM = "bank:confirm"  # подтвердить кредит
CB_BANK_LOANS = "bank:loans"  # мои кредиты
CB_BANK_REPAY_PREFIX = "bank:repay:"  # f"{...}{loan_id}" — погасить часть (ввод суммы)
CB_BANK_REPAY_ALL_PREFIX = "bank:repayall:"  # f"{...}{loan_id}" — погасить всё
CB_BANK_MY = "bank:my"  # мой банк / создать
CB_BANK_CREATE = "bank:create"  # мастер создания
CB_BANK_DEPOSIT = "bank:dep"  # пополнить капитал
CB_BANK_WITHDRAW = "bank:wd"  # забрать свободный капитал
CB_BANK_TERMS = "bank:terms"  # изменить условия
CB_BANK_CLOSE = "bank:close"  # закрыть банк
CB_BANK_CLOSE_YES = "bank:closeyes"

LOAN_ACTIVE = "active"  # идёт срок
LOAN_FROZEN = "frozen"  # просрочен: конфискация прошла, банда заморожена до погашения
LOAN_REPAID = "repaid"
LOAN_DEFAULTED = "defaulted"  # не погашен за заморозку — банда удалена, остаток списан
LOAN_OPEN: tuple[str, ...] = (LOAN_ACTIVE, LOAN_FROZEN)

LOCK_ACTION_BANK = "bank"

# Префиксы, которые замороженному игроку остаются доступны: экраны кредитов (погасить долг) и профиль.
FROZEN_ALLOWED_CALLBACKS: tuple[str, ...] = ("bank:",)


def key_frozen(user_id: int) -> str:
    """Флаг заморозки банды за долг (Redis): проверяют middleware бота и API на каждом действии."""
    return f"bank:frozen:{user_id}"
