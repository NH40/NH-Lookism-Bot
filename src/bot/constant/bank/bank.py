"""Банки игроков и кредиты (константы)."""
from __future__ import annotations

CB_BANK_OPEN = "bank:open"  # список банков
CB_BANK_PAGE_PREFIX = "bank:page:"  # f"{...}{page}"
CB_BANK_VIEW_PREFIX = "bank:view:"  # f"{...}{bank_id}" — карточка банка
CB_BANK_TAKE_PREFIX = "bank:take:"  # f"{...}{bank_id}:{kind}" — заявка (ввод суммы)
CB_BANK_DAYS_PREFIX = "bank:days:"  # f"{...}{days}" — срок в мастере заявки
CB_BANK_CONFIRM = "bank:confirm"  # подать заявку
CB_BANK_LOANS = "bank:loans"  # мои кредиты и заявки
CB_BANK_REPAY_PREFIX = "bank:repay:"  # f"{...}{loan_id}" — погасить часть (ввод суммы)
CB_BANK_REPAY_ALL_PREFIX = "bank:repayall:"  # f"{...}{loan_id}" — погасить всё
CB_BANK_CANCEL_PREFIX = "bank:cancel:"  # f"{...}{loan_id}" — отозвать заявку
CB_BANK_SIGN_PREFIX = "bank:sign:"  # f"{...}{loan_id}" — подписать договор
CB_BANK_DECLINE_PREFIX = "bank:decl:"  # f"{...}{loan_id}" — отказаться от договора
CB_BANK_APPROVE_PREFIX = "bank:ap:"  # f"{...}{loan_id}" — одобрить заявку
CB_BANK_APPROVE_TERMS_PREFIX = "bank:apt:"  # f"{...}{loan_id}" — одобрить со своими условиями
CB_BANK_REJECT_PREFIX = "bank:rj:"  # f"{...}{loan_id}" — отклонить заявку
CB_BANK_MY = "bank:my"  # мой банк / создать
CB_BANK_APPS = "bank:apps"  # заявки в мой банк
CB_BANK_CREATE = "bank:create"  # мастер создания
CB_BANK_DEPOSIT = "bank:dep"  # пополнить капитал
CB_BANK_WITHDRAW = "bank:wd"  # забрать свободный капитал
CB_BANK_TERMS = "bank:terms"  # изменить условия
CB_BANK_MEMBERS = "bank:members"  # участники
CB_BANK_MEMBER_ADD = "bank:madd"
CB_BANK_MEMBER_DEL_PREFIX = "bank:mdel:"  # f"{...}{user_id}"
CB_BANK_CLOSE = "bank:close"  # закрыть банк
CB_BANK_CLOSE_YES = "bank:closeyes"

KIND_FIXED = "fixed"  # сумма + X% один раз, сколько бы ни прошло
KIND_HOURLY = "hourly"  # X% каждый час на остаток тела до срока
KIND_DAILY = "daily"  # legacy: X% каждые сутки (кредиты до банков v2)
KINDS: tuple[str, ...] = (KIND_FIXED, KIND_HOURLY)

LOAN_PENDING = "pending"  # заявка ждёт банкира
LOAN_OFFERED = "offered"  # одобрено, договор ждёт подписи заёмщика (капитал зарезервирован)
LOAN_ACTIVE = "active"  # идёт срок
LOAN_FROZEN = "frozen"  # просрочен: конфискация прошла, банда заморожена, капает пеня
LOAN_SLAVE = "slave"  # заморозка вышла: 90% дохода уходит банкиру, пока долг не закрыт
LOAN_REPAID = "repaid"
LOAN_REJECTED = "rejected"
LOAN_CANCELLED = "cancelled"
LOAN_EXPIRED = "expired"
LOAN_DEFAULTED = "defaulted"  # legacy (банки v1: банда удалена)
LOAN_OPEN: tuple[str, ...] = (LOAN_ACTIVE, LOAN_FROZEN, LOAN_SLAVE)  # есть долг
LOAN_WAITING: tuple[str, ...] = (LOAN_PENDING, LOAN_OFFERED)

LOCK_ACTION_BANK = "bank"

# Префиксы, которые замороженному игроку остаются доступны: экраны кредитов (погасить долг).
FROZEN_ALLOWED_CALLBACKS: tuple[str, ...] = ("bank:",)


def key_frozen(user_id: int) -> str:
    """Флаг заморозки банды за долг (Redis): проверяют middleware бота и API на каждом действии."""
    return f"bank:frozen:{user_id}"
