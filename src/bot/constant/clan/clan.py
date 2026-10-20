"""Кланы (константы). Дизайн — `docs/design/clans.md`."""
from __future__ import annotations

# --- Ранги (как в UAP) ---
RANK_OWNER = "owner"
RANK_DEPUTY = "deputy"
RANK_CAPTAIN = "captain"
RANK_MEMBER = "member"
RANKS: tuple[str, ...] = (RANK_OWNER, RANK_DEPUTY, RANK_CAPTAIN, RANK_MEMBER)
MANAGER_RANKS: tuple[str, ...] = (RANK_OWNER, RANK_DEPUTY)  # заявки, приглашения, редактирование, казна, стройка, война
KICK_RANKS: tuple[str, ...] = (RANK_OWNER, RANK_DEPUTY, RANK_CAPTAIN)
RANK_LEVEL: dict[str, int] = {RANK_OWNER: 3, RANK_DEPUTY: 2, RANK_CAPTAIN: 1, RANK_MEMBER: 0}

# --- Здания ---
BUILDING_MARKET = "market"
BUILDING_TRAINING = "training"
BUILDING_LIBRARY = "library"
BUILDING_BARRACKS = "barracks"
BUILDING_TEMPLE = "temple"
BUILDING_WATCHTOWER = "tower"
BUILDING_DOJO = "dojo"
BUILDING_FORGE = "forge"
BUILDING_WALL = "wall"
# Пользователь 2026-10-12: 36 земель при сумме лимитов 29 — 7 земель были бесполезны; новые виды.
BUILDING_ALCHEMY = "alchemy"
BUILDING_HUNTERS = "hunters"
BUILDING_RECRUIT = "recruit"
BUILDINGS: tuple[str, ...] = (
    BUILDING_MARKET, BUILDING_TRAINING, BUILDING_LIBRARY, BUILDING_BARRACKS, BUILDING_TEMPLE,
    BUILDING_WATCHTOWER, BUILDING_DOJO, BUILDING_FORGE, BUILDING_WALL,
    BUILDING_ALCHEMY, BUILDING_HUNTERS, BUILDING_RECRUIT,
)

# --- Callback'и: ядро ---
CB_CLAN_OPEN = "clan:open"
CB_CLAN_CREATE = "clan:create"
CB_CLAN_FIND_PREFIX = "clan:find:"  # f"{...}{page}"
CB_CLAN_VIEW_PREFIX = "clan:view:"  # f"{...}{clan_id}"
CB_CLAN_APPLY_PREFIX = "clan:apply:"
CB_CLAN_CANCEL_APP_PREFIX = "clan:unapply:"
CB_CLAN_MEMBERS = "clan:members"
CB_CLAN_REQUESTS = "clan:requests"
CB_CLAN_ACCEPT_PREFIX = "clan:acc:"  # f"{...}{user_id}"
CB_CLAN_REJECT_PREFIX = "clan:rej:"
CB_CLAN_INVITE = "clan:invite"
CB_CLAN_MY_INVITES = "clan:invites"
CB_CLAN_ACCEPT_INVITE_PREFIX = "clan:accinv:"  # f"{...}{clan_id}"
CB_CLAN_DECLINE_INVITE_PREFIX = "clan:decinv:"
CB_CLAN_RANKS = "clan:ranks"
CB_CLAN_RANK_PREFIX = "clan:rank:"  # f"{...}{user_id}" | f"{...}{user_id}:{rank}"
CB_CLAN_TRANSFER = "clan:transfer"
CB_CLAN_TRANSFER_PREFIX = "clan:tr:"  # f"{...}{user_id}" | f"{...}{user_id}:ok"
CB_CLAN_DELETE = "clan:delete"
CB_CLAN_DELETE_CONFIRM = "clan:delete:ok"
CB_CLAN_KICK = "clan:kick"
CB_CLAN_KICK_PREFIX = "clan:kk:"  # f"{...}{user_id}" | f"{...}{user_id}:ok"
CB_CLAN_EDIT = "clan:edit"
CB_CLAN_EDIT_NAME = "clan:edit:name"
CB_CLAN_EDIT_DESCRIPTION = "clan:edit:desc"
CB_CLAN_EDIT_IMAGE = "clan:edit:img"
CB_CLAN_LEAVE = "clan:leave"
CB_CLAN_LEAVE_CONFIRM = "clan:leave:ok"
CB_CLAN_TOP_PREFIX = "clan:top:"  # f"{...}{page}"
CB_CLAN_EXCHANGE = "clan:ex"  # обменник: выбрать участника
CB_CLAN_EXCHANGE_MEMBER_PREFIX = "clan:exm:"  # f"{...}{user_id}"
CB_CLAN_EXCHANGE_RES_PREFIX = "clan:exr:"  # f"{...}{user_id}:{resource}"

# --- Callback'и: земли, казна, магазин, журнал ---
CB_CLAN_LANDS = "clan:lands"
CB_CLAN_BUY_LAND = "clan:land:buy"
CB_CLAN_BUILD_PREFIX = "clan:bld:"  # f"{...}{kind}" — карточка здания
CB_CLAN_BUILD_UP_PREFIX = "clan:bup:"  # f"{...}{kind}" — построить ещё
CB_CLAN_BUILD_DOWN_PREFIX = "clan:bdn:"  # f"{...}{kind}" — снести одно
CB_CLAN_TREASURY = "clan:treasury"
CB_CLAN_DONATE_COINS = "clan:give"  # внести NHCoin в казну (ввод суммы)
CB_CLAN_SHOP = "clan:shop"
CB_CLAN_SHOP_TICKETS = "clan:shtk"  # дальше — ввод количества (ClanStates.waiting_shop_tickets)
CB_CLAN_SHOP_POTION_PREFIX = "clan:shpt:"  # f"{...}{kind}:{tier}"
CB_CLAN_SHOP_MERCS = "clan:shmc"  # наёмники в роту: выбрать ранг
CB_CLAN_SHOP_MERCS_PREFIX = "clan:shmr:"  # f"{...}{rank}" — ввод количества
CB_CLAN_LOG = "clan:log"
CB_CLAN_LEVEL_BUY = "clan:lvlbuy"
CB_CLAN_LEVELS = "clan:levels"

# --- Callback'и: рота и война ---
CB_CLAN_GARRISON = "clan:gar"
CB_CLAN_GAR_PUT = "clan:gar:put"  # выбрать: статисты / уники
CB_CLAN_GAR_PUT_SQUAD_PREFIX = "clan:gps:"  # f"{...}{StatistKey}"
CB_CLAN_GAR_PUT_CARDS = "clan:gar:putc"
CB_CLAN_GAR_PUT_CARD_PREFIX = "clan:gpc:"  # f"{...}{card_code}"
CB_CLAN_GAR_TAKE = "clan:gar:take"
CB_CLAN_GAR_TAKE_SQUAD_PREFIX = "clan:gts:"  # f"{...}{StatistKey}"
CB_CLAN_GAR_TAKE_CARD_PREFIX = "clan:gtc:"  # f"{...}{card_code}"
CB_CLAN_GAR_REQUEST = "clan:gar:req"  # рядовой просит доступ к роте
CB_CLAN_GAR_ACCESS = "clan:gar:acc"  # владелец/зам: запросы доступа
CB_CLAN_GAR_APPROVE_PREFIX = "clan:gok:"  # f"{...}{user_id}"
CB_CLAN_GAR_DENY_PREFIX = "clan:gno:"  # f"{...}{user_id}"
CB_CLAN_GAR_REVOKE_PREFIX = "clan:grv:"  # f"{...}{user_id}" — владелец отнимает право
# Без одобрения забирают из роты эти ранги; рядовым — с одобрения владельца/зама (один раз).
GARRISON_FREE_RANKS: tuple[str, ...] = ("owner",)  # остальным — право от владельца (2026-10-12)
CB_CLAN_WAR = "clan:war"
CB_CLAN_WAR_TARGETS_PREFIX = "clan:wt:"  # f"{...}{page}"
CB_CLAN_WAR_ATTACK_PREFIX = "clan:wa:"  # f"{...}{clan_id}" | f"{...}{clan_id}:ok"

# Предмет роты.
GARRISON_STATIST = "statist"
GARRISON_CARD = "card"

# Правило 2: действия, двигающие ресурсы или людей, — Redis-лок на клик.
LOCK_ACTION_CLAN = "clan"

# Статистика вклада участников (2026-10-21): f"{CB_CLAN_STATS_PREFIX}{сортировка}".
CB_CLAN_STATS_PREFIX = "clan:stats:"
STATS_SORT_TREASURY = "treasury"
STATS_SORT_GARRISON = "garrison"
STATS_SORT_SPENT = "spent"
STATS_SORT_WARS = "wars"
STATS_SORT_ACTIVITY = "activity"
STATS_SORTS = (STATS_SORT_TREASURY, STATS_SORT_GARRISON, STATS_SORT_SPENT, STATS_SORT_WARS, STATS_SORT_ACTIVITY)
