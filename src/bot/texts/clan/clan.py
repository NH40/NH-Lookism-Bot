"""Кланы (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

from bot.constant.clan import (
    BUILDING_ALCHEMY,
    BUILDING_HUNTERS,
    BUILDING_RECRUIT,
    BUILDING_BARRACKS,
    BUILDING_DOJO,
    BUILDING_FORGE,
    BUILDING_LIBRARY,
    BUILDING_MARKET,
    BUILDING_TEMPLE,
    BUILDING_TRAINING,
    BUILDING_WALL,
    BUILDING_WATCHTOWER,
    RANK_CAPTAIN,
    RANK_DEPUTY,
    RANK_MEMBER,
    RANK_OWNER,
)

RANK_EMOJI = {RANK_OWNER: "👑", RANK_DEPUTY: "🥈", RANK_CAPTAIN: "🎖", RANK_MEMBER: "👤"}
RANK_NAME = {RANK_OWNER: "Владелец", RANK_DEPUTY: "Заместитель", RANK_CAPTAIN: "Капитан", RANK_MEMBER: "Участник"}

BUILDING_NAMES: dict[str, str] = {
    BUILDING_MARKET: "💰 Рынок",
    BUILDING_TRAINING: "🏋 Тренировочный зал",
    BUILDING_LIBRARY: "📚 Библиотека",
    BUILDING_BARRACKS: "🪖 Казарма",
    BUILDING_TEMPLE: "🍀 Храм удачи",
    BUILDING_WATCHTOWER: "🗼 Сторожевая башня",
    BUILDING_DOJO: "🥋 Додзё",
    BUILDING_FORGE: "🔨 Кузница",
    BUILDING_WALL: "🧱 Стена",
    BUILDING_ALCHEMY: "⚗️ Алхимическая лаборатория",
    BUILDING_HUNTERS: "🏹 Гильдия охотников",
    BUILDING_RECRUIT: "📯 Вербовочный пункт",
}
BUILDING_ABOUT: dict[str, str] = {
    BUILDING_MARKET: "+3% к доходу бизнеса каждому участнику за здание.",
    BUILDING_TRAINING: "+2 п.п. к шансам тренировки статистов каждому участнику за здание.",
    BUILDING_LIBRARY: "+5% очков развития с личной тренировки за здание.",
    BUILDING_BARRACKS: "+2% к мощи каждого бойца армии участников за здание.",
    BUILDING_TEMPLE: "+2% к шансу поднять редкость уника при крутке за здание.",
    BUILDING_WATCHTOWER: "Призывает на карту клановых боссов — их видят и бьют только участники. Чем больше башен, тем чаще.",
    BUILDING_DOJO: "Зовёт на карту клановых учителей — только для участников. Чем больше додзё, тем чаще.",
    BUILDING_FORGE: "+5% к атаке клановой роты, когда клан нападает.",
    BUILDING_WALL: "+5% к прочности и гашению урона клановой роты, когда на клан нападают.",
    BUILDING_ALCHEMY: "Зелья дешевле на 4% и действуют на 5% дольше каждому участнику за здание.",
    BUILDING_HUNTERS: "+5% фрагментов с боссов каждому участнику за здание.",
    BUILDING_RECRUIT: "−4% к КД вербовки статистов каждому участнику за здание.",
}

# --- без клана ---
NO_CLAN = (
    "🏰 <b>Клан</b>\n━━━━━━━━━━━━━━━━━━\n"
    "У тебя нет клана. Основать свой — {cost} 🪙: у клана будет земля под здания, казна, "
    "клановая рота и войны за территории."
)
BTN_CREATE = "➕ Основать клан · {cost} 🪙"
BTN_FIND = "🔍 Найти клан"
BTN_MY_INVITES = "✉️ Приглашения ({count})"
BTN_TOP = "🏆 Топ кланов"
CREATE_PROMPT = "Название клана ({min}–{max} символов)."
NAME_INVALID = "Название — от {min} до {max} символов, в одну строку."
CREATED = "🏰 Клан «{name}» основан! Земель: {lands}."

# --- карточка ---
CLAN_CARD = (
    "🏰 <b>{name}</b>{crown}\n"
    "━━━━━━━━━━━━━━━━━━\n{description}\n━━━━━━━━━━━━━━━━━━\n"
    "👥 Участники: <b>{members}/{max_members}</b> · 👑 {owner}\n"
    "🌍 Земли: <b>{lands}/{max_lands}</b> · 🏗 Зданий: {used}\n"
    "💰 Казна: <b>{treasury}</b> 🪙 · ⚔️ Мощь роты: <b>{power}</b>\n"
    "💎 Уровень клана: <b>{donate_level}/5</b>"
    "{me}"
)
CARD_ME = "\n━━━━━━━━━━━━━━━━━━\n🎖 Твой ранг: <b>{rank}</b>"
CARD_SHARE = " · доля дохода: +{share} 🪙 (заберётся с доходом)"
NO_DESCRIPTION = "<i>Описание не добавлено.</i>\n"
BTN_MEMBERS = "👥 Участники"
BTN_GARRISON = "⚔️ Рота"
BTN_LANDS = "🌍 Земли и здания"
BTN_TREASURY = "💰 Казна"
BTN_SHOP = "🛒 Магазин клана"
BTN_WAR = "🏴 Война"
BTN_EXCHANGE = "🔄 Обменник"
BTN_LOG = "📜 Журнал"
BTN_LEVELS = "💎 Уровни клана"
BTN_REQUESTS = "📬 Заявки ({count})"
BTN_INVITE = "✉️ Пригласить"
BTN_EDIT = "✏️ Редактировать"
BTN_RANKS = "🎖 Ранги"
BTN_KICK = "👢 Исключить"
BTN_LEAVE = "🚪 Покинуть клан"
BTN_APPLY = "📨 Подать заявку"
BTN_CANCEL_APP = "❌ Отменить заявку"
BTN_CONFIRM = "✅ Подтвердить"
BTN_PREV = "◀️"
BTN_NEXT = "▶️"

# --- поиск / топ ---
FIND_HEADER = "🔍 <b>Кланы</b> (стр. {page}/{pages})\n━━━━━━━━━━━━━━━━━━\n"
TOP_HEADER = "🏆 <b>Топ кланов</b> — по землям (стр. {page}/{pages})\n━━━━━━━━━━━━━━━━━━\n"
CLAN_LINE = "🏰 <b>{place}.</b> {name} — 🌍 {lands}, 👥 {members}\n"
CLANS_EMPTY = "📭 <i>Кланов пока нет — стань первым!</i>"

# --- участники ---
MEMBERS_HEADER = "👥 <b>Участники «{name}»</b>\n━━━━━━━━━━━━━━━━━━\n"
MEMBER_LINE = "{emoji} {name}{username} — {rank}\n"

# --- заявки / приглашения ---
REQUESTS_HEADER = "📬 <b>Заявки в клан</b>\n━━━━━━━━━━━━━━━━━━\n"
REQUESTS_EMPTY = "📭 <i>Заявок нет.</i>"
BTN_ACCEPT = "✅ {name}"
BTN_REJECT = "❌ {name}"
INVITE_PROMPT = "Напиши @юзернейм игрока, которого приглашаешь."
INVITE_SENT = "✉️ Приглашение отправлено {name}."
MY_INVITES_HEADER = "✉️ <b>Приглашения в кланы</b>\n━━━━━━━━━━━━━━━━━━\n"
MY_INVITES_EMPTY = "📭 <i>Приглашений нет.</i>"
BTN_ACCEPT_INVITE = "✅ «{name}»"
BTN_DECLINE_INVITE = "❌ «{name}»"
PUSH_APPLICATION = "📬 {name} подал(а) заявку в клан «{clan}»."
PUSH_INVITE = "✉️ Клан «{clan}» приглашает тебя! Открой 🏰 Клан → Приглашения."
PUSH_ACCEPTED = "🏰 Тебя приняли в клан «{clan}»!"
PUSH_KICKED = "👢 Тебя исключили из клана «{clan}»."
PUSH_DELETED = "🗑 Клан «{clan}» распущен владельцем."
PUSH_EXCHANGE = "🔄 {name} передал(а) тебе {amount} через обменник клана."

# --- ранги / передача / удаление / кик ---
RANKS_HEADER = "🎖 <b>Ранги</b> — выбери участника:"
RANK_PICK = "{name} — сейчас {rank}. Назначить:"
TRANSFER_PROMPT = "Кому передать клан?"
TRANSFER_CONFIRM = "Передать клан «{clan}» игроку {name}? Ты станешь участником."
DELETE_CONFIRM = "⚠️ Распустить клан «{clan}»? Земли, здания, казна и рота пропадут, все участники выйдут. Это необратимо."
KICK_PROMPT = "Кого исключить?"
KICK_EMPTY = "Исключать некого."
KICK_CONFIRM = "Исключить {name} из клана?"
LEAVE_CONFIRM = "Покинуть клан «{clan}»?"
BTN_TRANSFER = "👑 Передать клан"
BTN_DELETE = "🗑 Распустить клан"

# --- редактирование ---
EDIT_MENU = "✏️ <b>Редактирование клана</b>"
BTN_EDIT_NAME = "Название"
BTN_EDIT_DESCRIPTION = "Описание"
BTN_EDIT_IMAGE = "🖼 Аватарка"
EDIT_DESCRIPTION_PROMPT = "Новое описание (до {max} символов)."
EDIT_IMAGE_PROMPT = "Пришли картинку клана (фото)."
EDITED = "✅ Сохранено."

# --- земли и здания ---
LANDS_SCREEN = (
    "🌍 <b>Земли клана</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Земель: <b>{lands}/{max_lands}</b> · занято зданиями: {used} · свободно: {free}\n"
    "💰 Казна: <b>{treasury}</b> 🪙\n━━━━━━━━━━━━━━━━━━\n"
    "💡 Одна земля — одно здание. Освоить землю можно за казну до {buy_max}; каждый уровень клана — "
    "ещё +{per_level} к потолку. В войне земли можно отнять и потерять.\n━━━━━━━━━━━━━━━━━━\n"
    "{buildings}"
)
LANDS_BUILDING_LINE = "🏗 {name}: <b>{count}/{max}</b>\n"
LANDS_NO_BUILDINGS = "🏚 <i>Зданий пока нет.</i>"
BTN_BUY_LAND = "🌍 Освоить землю · {price} 🪙"
BTN_BUILDING = "{name} · {count}/{max}"
BUILDING_SCREEN = (
    "{name}\n<i>{about}</i>\n━━━━━━━━━━━━━━━━━━\n"
    "🏗 Построено: <b>{count}/{max}</b>\n"
    "{next}"
)
BUILDING_NEXT = "Следующее — {price} 🪙 из казны."
BUILDING_FULL = "Больше не построить."
BTN_BUILD = "🏗 Построить · {price} 🪙"
BTN_DEMOLISH = "🧱 Снести одно (+{refund} 🪙)"

# --- казна ---
TREASURY_SCREEN = (
    "💰 <b>Казна клана</b>: <b>{treasury}</b> 🪙\n━━━━━━━━━━━━━━━━━━\n"
    "Вносить может любой участник; тратят владелец и заместитель — на земли, здания и магазин "
    "клана.\n👛 У тебя: <b>{coins}</b> 🪙"
)
BTN_DONATE = "💰 Внести в казну"
DONATE_PROMPT = "Сколько NHCoin внести в казну? У тебя {coins} 🪙."
DONATED = "💰 Внесено. Казна: {treasury} 🪙."

# --- магазин клана ---
SHOP_SCREEN = (
    "🛒 <b>Магазин клана</b> — из казны ({treasury} 🪙), покупают владелец и заместитель.\n━━━━━━━━━━━━━━━━━━\n"
    "🎟 Тикеты — каждому участнику ({members}).\n"
    "🧪 Зелья — выпиваются сразу у всех участников.\n"
    "⚔️ Наёмники — навсегда в клановую роту."
)
BTN_SHOP_TICKETS = "🎟 Всем по {tickets} · {price} 🪙"
BTN_SHOP_POTION = "{name} {roman} всем · {price} 🪙"
BTN_SHOP_MERCS = "📜 Контракты в роту"
MERCS_SCREEN = (
    "📜 <b>Контракты в роту</b> — бойцы на {hours} ч: воюют за роту и гибнут в войне, по сроку уходят. "
    "Забрать их себе не может никто. Ранг — до твоего потолка по влиянию ({ceiling}):"
)
BTN_MERCS_RANK = "{rank} · {price} 🪙"
MERCS_PROMPT = "Контракт {rank} на {hours} ч: {price} 🪙 за бойца из казны ({treasury} 🪙). Сколько нанять? Напиши число."
SHOP_DONE = "🛒 Куплено за {price} 🪙 из казны."

# --- журнал / уровни ---
LOG_SCREEN = "📜 <b>Журнал клана</b>\n━━━━━━━━━━━━━━━━━━\n{rows}"
LOG_LINE = "{time} {text}\n"
LOG_EMPTY = "📭 <i>Записей нет.</i>"
LEVELS_SCREEN = (
    "💎 <b>Уровни клана</b> — сейчас <b>{level}/5</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Каждый уровень — бафы всем участникам, +4 к потолку земель и сила роты в войне. Купить "
    "может любой участник за 💎 донат-коины. Уровень привязан к купившему: ушёл из клана — "
    "уровень пропадает, а донат возвращается ему.\n━━━━━━━━━━━━━━━━━━\n{levels}"
    "━━━━━━━━━━━━━━━━━━\n👥 Купили: {buyers}"
)
LEVELS_NO_BUYERS = "<i>пока никто</i>"
BTN_BUY_LEVEL = "💎 Уровень {n} — {price} 💎"
LEVEL_BOUGHT_ALERT = "💎 Уровень клана поднят до {level}!"
LEVEL_LINE = "{mark} <b>{n}</b>: {effect}\n"

# --- рота ---
GARRISON_SCREEN = (
    "⚔️ <b>Клановая рота</b> — мощь клана: <b>{power}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Участники вносят сюда статистов и уников; забирать бойцов может владелец и те, кому он выдал "
    "право (через сутки после вступления). Контрактников роты не забирает никто. Именно рота "
    "сражается в войне кланов за земли.\n━━━━━━━━━━━━━━━━━━\n"
    "{statists}{cards}{contracts}{tenure}"
)
GARRISON_STATISTS = "👥 <b>Статисты:</b>\n{rows}\n"
GARRISON_CARDS = "🃏 <b>Уники:</b>\n{rows}\n"
GARRISON_ROW = "🔹 {name} — {quantity} (мощь {power})\n"
GARRISON_EMPTY = "📭 <i>Рота пуста.</i>\n"
GARRISON_CONTRACTS = "📜 <b>Контрактники</b> (не забираются):\n{rows}\n"
GARRISON_CONTRACT_ROW = "🔸 {rank} — {quantity} (мощь {power}), ещё {countdown}\n"
GARRISON_TENURE = "\n⏳ Забирать бойцов сможешь через {countdown}."
GARRISON_NEEDS_APPROVAL = "\n🔑 Забирать бойцов можно только с правом, которое выдаёт владелец клана."
GARRISON_PENDING = "\n🔑 Запрос доступа к роте ждёт ответа владельца."
BTN_GAR_REQUEST = "🔑 Запросить доступ"
BTN_GAR_ACCESS = "🔑 Доступ к роте ({count})"
BTN_GAR_ACCESS_PLAIN = "🔑 Доступ к роте"
GAR_ACCESS_HEADER = (
    "🔑 <b>Доступ к роте</b>\nЗабирать бойцов из роты может только тот, кому ты выдал право. "
    "Право можно отнять в любой момент. 🔔 — участник просит доступ.\n\n"
)
GAR_ACCESS_EMPTY = "📭 <i>В клане нет других участников.</i>"
BTN_GAR_ACCESS_ON = "✅ {name} — отнять"
BTN_GAR_ACCESS_OFF = "{bell}🔒 {name} — выдать"
PUSH_GAR_REVOKED = "🔑 Владелец клана отнял у тебя доступ к роте."
BTN_GAR_APPROVE = "✅ {name}"
BTN_GAR_DENY = "❌ {name}"
PUSH_GAR_REQUEST = "🔑 {name} просит доступ к клановой роте — 🏰 Клан → Доступ к роте."
PUSH_GAR_APPROVED = "🔑 Владелец клана выдал тебе доступ к роте — теперь бойцов можно забирать."
PUSH_GAR_DENIED = "🔑 В доступе к клановой роте отказано."
GAR_REQUESTED_ALERT = "Запрос отправлен владельцу и заместителю"
BTN_GAR_PUT = "📥 Внести"
BTN_GAR_TAKE = "📤 Забрать"
GAR_PUT_PICK = "📥 <b>Что внести в роту?</b>"
BTN_GAR_PUT_STATISTS = "👥 Статистов"
BTN_GAR_PUT_CARDS = "🃏 Уников"
GAR_PICK_SQUAD = "👥 <b>Какой отряд?</b> Бойцы берутся из защиты, потом из атаки."
GAR_PICK_CARD = "🃏 <b>Какого уника?</b> Копии берутся из армии (не с позиций отряда)."
GAR_PICK_TAKE = "📤 <b>Кого забрать из роты?</b> Бойцы встанут в твой лагерь защиты."
GAR_NOTHING = "Нечего выбрать."
GAR_AMOUNT = "{item}: доступно {have}. Сколько? Напиши число."
GAR_DONE = "⚔️ Готово."
BTN_ITEM = "{name} · {quantity}"

# --- война ---
WAR_SCREEN = (
    "🏴 <b>Война кланов</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Раз в сутки владелец или заместитель может напасть на другой клан. Сражаются клановые роты; "
    "Кузницы усиливают атаку, Стены — защиту. Победитель забирает часть земель и {treasury_pct}% казны "
    "проигравшего, а здания на потерянных землях рушатся. После нападения у клана щит {shield} ч.\n━━━━━━━━━━━━━━━━━━\n"
    "⚔️ Мощь твоей роты: <b>{power}</b>\n{status}\n━━━━━━━━━━━━━━━━━━\n{history}"
)
WAR_READY = "✅ Можно нападать."
WAR_COOLDOWN = "⏳ Следующее нападение через {countdown}."
WAR_SHIELD = "\n🛡 Клан под щитом ещё {countdown}."
WAR_HISTORY_HEAD = "📜 <b>Последние войны:</b>\n"
WAR_HISTORY_LINE = "{mark} «{attacker}» → «{defender}»: {result}\n"
WAR_HISTORY_WIN = "победа нападающих, земель {lands}"
WAR_HISTORY_LOSS = "оборона устояла"
WAR_HISTORY_EMPTY = "📭 <i>Войн ещё не было.</i>"
BTN_WAR_TARGETS = "🎯 Выбрать цель"
WAR_TARGETS = "🎯 <b>На кого нападаем?</b> (стр. {page}/{pages})"
BTN_TARGET = "{shield}{name} · 🌍 {lands} · 👥 {members}"
WAR_CONFIRM = "🏴 Напасть на «{name}» (🌍 {lands})? Роты сразятся сразу, потери — с рот."
BTN_ATTACK = "⚔️ В атаку"
WAR_RESULT = (
    "🏴 <b>«{attacker}» против «{defender}»</b>\n━━━━━━━━━━━━━━━━━━\n"
    "⚔️ Роты: <b>{a_power}</b> против <b>{d_power}</b> · раундов {rounds}\n"
    "💀 Потери: {a_dead} у нападающих, {d_dead} у защитников\n━━━━━━━━━━━━━━━━━━\n"
    "{verdict}"
)
WAR_VERDICT_WIN = "🏆 Победа нападающих: отнято земель {taken} (досталось {gained}), казна +{treasury} 🪙.{buildings}"
WAR_VERDICT_LOSS = "🛡 Оборона устояла — земли остались у защитников."
WAR_BUILDINGS_LOST = "\nРухнули здания: {list}."

# --- обменник ---
EXCHANGE_PICK = "🔄 <b>Обменник</b>\n━━━━━━━━━━━━━━━━━━\n<i>Кому передать ресурс?</i>"
EXCHANGE_NONE = "📭 В клане больше никого нет."  # popup — без HTML
EXCHANGE_RES = "🔄 <b>Обменник</b>\n━━━━━━━━━━━━━━━━━━\n👤 Игрок: <b>{name}</b>\n<i>Что передать?</i>"
EXCHANGE_AMOUNT = "🔄 Сколько {res} передать игроку <b>{name}</b>?\n👛 У тебя: <b>{have}</b>"
EXCHANGED = "🔄 Передано {amount} игроку {name}."

AMOUNT_INVALID = "Нужно целое число больше нуля. Попробуй ещё раз."

# --- popup (без HTML) ---
ERRORS: dict[str, str] = {
    "busy": "Обрабатываю…",
    "not_in_clan": "Ты не в клане.",
    "no_rights": "Недостаточно прав.",
    "already_in_clan": "Ты уже в клане.",
    "name_taken": "Такое название уже занято.",
    "no_coins": "Не хватает NHCoin: нужно {value}.",
    "no_donate": "Не хватает донат-коинов: нужно {value}. Пополнить — /donate",
    "donate_max": "У клана уже максимальный уровень.",
    "clan_gone": "Клан не найден.",
    "applied_elsewhere": "У тебя уже есть заявка в другой клан — сначала отмени её.",
    "clan_full": "В клане уже {value} участников.",
    "request_gone": "Заявка уже неактуальна.",
    "no_player": "Игрок не найден.",
    "target_in_clan": "Этот игрок уже в клане.",
    "not_member": "Игрок не в твоём клане.",
    "deputy_taken": "Заместитель может быть только один.",
    "higher_rank": "Нельзя исключить игрока с таким же или более высоким рангом.",
    "owner_must_transfer": "Сначала передай клан другому участнику.",
    "not_top": "Аватарку ставят только кланы из топ-{value}.",
    "bad_amount": "Неверное количество.",
    "lands_max": "Земель уже максимум ({value}).",
    "no_treasury": "Не хватает в казне: нужно {value} NHCoin.",
    "bad_building": "Неизвестное здание.",
    "no_free_land": "Нет свободной земли — освой новую.",
    "building_max": "Больше {value} таких зданий не построить.",
    "no_building": "Таких зданий нет.",
    "target_gone": "Этот игрок уже не в твоём клане.",
    "not_enough": "Столько нет.",
    "bad_item": "Неверный товар.",
    "tenure": "Забирать из роты можно через сутки после вступления.",
    "needs_approval": "Сначала нужно разовое одобрение владельца или заместителя — запроси доступ.",
    "approval_pending": "Запрос доступа уже ждёт ответа владельца или заместителя.",
    "access_not_needed": "Тебе одобрение не нужно.",
    "own_clan": "Это твой клан.",
    "war_cooldown": "Клан уже нападал — следующее нападение позже.",
    "shielded": "Этот клан под щитом после недавнего нападения.",
    "empty_garrison": "Рота пуста — нападать некем. Внесите бойцов в роту.",
}
LEFT_ALERT = "Ты покинул(а) клан"
ACCEPTED_ALERT = "Принят(а) в клан"
DONE_ALERT = "Готово"
