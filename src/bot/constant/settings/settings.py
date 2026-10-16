"""Настройки (константы): категории пушей и callback'и экрана уведомлений.

Пользователь 2026-10-03: «для всех уведомлений, которые приходят игрокам, специальные
настройки… включать и выключать… абсолютно все, которые есть в игре». Каждая категория —
ключ в `users.notify_muted` (массив ВЫКЛЮЧЕННЫХ категорий: по умолчанию включено всё).
"""
from __future__ import annotations

NOTIFY_PVP_CALL = "pvp_call"  # на твой район/город напали — вызов с кнопкой «Принять бой»
NOTIFY_PVP_REPORT = "pvp_report"  # итог PvP-боя (и нападающему, и защитнику)
NOTIFY_THRONE = "throne"  # бой за твой трон императора
NOTIFY_WAR_CALL = "war_call"  # тебе объявили войну императоров
NOTIFY_WAR_REPORT = "war_report"  # итог войны императоров
NOTIFY_SABOTAGE = "sabotage"  # саботаж против тебя (императора)
NOTIFY_MASTERY = "mastery"  # новый этап «Преодоления стены»
NOTIFY_BOSS = "boss"  # босс на карте
NOTIFY_TEACHER = "teacher"  # учитель техник на карте
NOTIFY_SCHOOL = "school"  # учитель статистов на карте
NOTIFY_POTION = "potion"  # авто-зелье выключилось
NOTIFY_EXCHANGE = "exchange"  # биржа: продажи, ставки, аукционы, обмены
NOTIFY_CLAN = "clan"  # клан: заявки, приглашения, приём, исключение, обменник, роспуск
NOTIFY_CLAN_WAR = "clan_war"  # война кланов: нападения и итоги
NOTIFY_CD_BATTLE = "cd_battle"  # КД сражений прошёл — можно атаковать
NOTIFY_CD_PERSONAL = "cd_personal"  # личная тренировка готова
NOTIFY_CD_EXTRAS = "cd_extras"  # тренировка статистов готова
NOTIFY_ARKHANGEL = "arkhangel"  # абсолют Архангел принёс часовой доход

NOTIFY_CATEGORIES: tuple[str, ...] = (
    NOTIFY_PVP_CALL,
    NOTIFY_PVP_REPORT,
    NOTIFY_THRONE,
    NOTIFY_WAR_CALL,
    NOTIFY_WAR_REPORT,
    NOTIFY_SABOTAGE,
    NOTIFY_MASTERY,
    NOTIFY_BOSS,
    NOTIFY_TEACHER,
    NOTIFY_SCHOOL,
    NOTIFY_POTION,
    NOTIFY_EXCHANGE,
    NOTIFY_CLAN,
    NOTIFY_CLAN_WAR,
    NOTIFY_CD_BATTLE,
    NOTIFY_CD_PERSONAL,
    NOTIFY_CD_EXTRAS,
    NOTIFY_ARKHANGEL,
)

CB_NOTIFY_OPEN = "settings:notify"
CB_NOTIFY_TOGGLE_PREFIX = "settings:notify:t:"
CB_NOTIFY_ALL_ON = "settings:notify:on"
CB_NOTIFY_ALL_OFF = "settings:notify:off"
