"""Арт для боссов и учителей на карте: код -> путь под `assets/` (None — арта ещё нет).

Приоритет у выделенного файла `assets/boss/`, `assets/teacher_ut/` (учителя техник) или
`assets/teacher_statist/` (учителя статистов) — имя = код или алиас, регистр не важен — положил
файл, и арт подхватился без правок кода (проверка наличия — в API при запросе). Эти словари —
временные подставные портреты из карточек, пока нет собственных артов.
"""
from __future__ import annotations

from bot.constant.event import BOSS_ELITE, BOSS_GAPRYONG, BOSS_JINYEONG
from bot.constant.school import SCHOOL_AGILITY, SCHOOL_SPEED, SCHOOL_STRENGTH, SCHOOL_TECHNIQUE
from bot.constant.unique_technique import (
    TECH_BEAST,
    TECH_BLADE_HANDS,
    TECH_INVISIBLE,
    TECH_KYOKUSHIN,
    TECH_MA_TAESU,
    TECH_MIDNIGHT,
    TECH_MUAY_THAI,
    TECH_NINJUTSU,
    TECH_ONE_STEP,
    TECH_OVERCOME,
    TECH_TAEKWONDO,
)

BOSS_ART: dict[str, str | None] = {
    BOSS_GAPRYONG: "card/peak/Gapryong_Prime.png",
    BOSS_JINYEONG: "card/gen_zero/Jinyoung_Prime.png",
    BOSS_ELITE: "card/gen_zero/Elite_Prime.png",
}

TECHNIQUE_TEACHER_ART: dict[str, str | None] = {
    TECH_BEAST: "card/gen_zero/TomLee_Base.png",
    TECH_INVISIBLE: "card/gen_zero/Elite_Prime.png",
    TECH_OVERCOME: "card/strong_king/Jinrang_Conviction.png",
    TECH_TAEKWONDO: "card/legend/Hansu_0%.png",
    TECH_BLADE_HANDS: "card/strong_king/Jinchang_Prime.png",
    TECH_MUAY_THAI: "card/legend/Brekdak_Legend.png",
    TECH_NINJUTSU: None,
    TECH_KYOKUSHIN: None,
    TECH_MA_TAESU: None,
    TECH_ONE_STEP: None,
    TECH_MIDNIGHT: None,
}

SCHOOL_TEACHER_ART: dict[str, str | None] = {
    SCHOOL_STRENGTH: "card/gen_zero/Baekho_Prime.png",
    SCHOOL_AGILITY: "card/gen_zero/Elite_Prime.png",
    SCHOOL_SPEED: None,  # Мусаши — карты нет, ждёт арт в assets/teacher_statist
    SCHOOL_TECHNIQUE: "card/legend/Hansu_0%.png",
}

# Альтернативные имена файлов выделенного арта (`assets/boss/`, `assets/teacher/`): файл
# можно назвать кодом или любым алиасом, регистр не важен.
ART_ALIASES: dict[str, tuple[str, ...]] = {
    BOSS_GAPRYONG: ("gapryong", "gapren", "gauren"),
    BOSS_JINYEONG: ("jinyeong", "jinong", "jinyoung", "jinnen"),
    BOSS_ELITE: ("elite",),
}
