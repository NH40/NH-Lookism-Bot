"""Техники мастерства (пользователь 2026-11-19): у каждого из 4 мастерств дерево 3 ступени × 3 техники Lookism.

Открывается после первого этапа «Преодоления стены» этого мастерства (в мастерство вложено хотя бы 1 очко).
На ступени N выбирается одна из трёх техник, ступени по порядку, без ограничений между ветками.
Ступень N стоит 20 × N фрагментов техник. Эффекты в бою — в обновлении битвы (структура атаки меняется),
сейчас техника только изучается и видна в билде.
"""
from __future__ import annotations

from dataclasses import dataclass

MASTERY_TECH_COST_PER_TIER = 20  # фрагменты техник × ступень
MASTERY_TECH_TIERS = 3


@dataclass(frozen=True, slots=True)
class MasteryTech:
    code: str
    name: str
    about: str


# мастерство → ступени → 3 техники
MASTERY_TREES: dict[str, tuple[tuple[MasteryTech, ...], ...]] = {
    "strength": (
        (MasteryTech("ssireum", "Ссирым Джерри Квона", "Захват и бросок через корпус — грубая сила против строя."),
         MasteryTech("yakuza", "Стиль якудза Ган Пака", "Удары без правил: каждый следующий тяжелее."),
         MasteryTech("mandeok_brute", "Грубая сила Мандока", "Чистая мощь: удар, который не держат блоком.")),
        (MasteryTech("king_fist", "Кулак Короля Сокду", "Удар короля Сеула старой эпохи — ломает защиту."),
         MasteryTech("vinjin_kick", "Удар Вин Джина", "Тхэквондо с силой ссирыма — пробивной удар ногой."),
         MasteryTech("heavy_hand", "Тяжёлая рука Ган Пака", "Кёкушин-удар с весом всего тела.")),
        (MasteryTech("gapryong_fist", "Кулак Ким Гапрёна", "Сила легенды первого поколения — удар сквозь стену."),
         MasteryTech("mandeok_quake", "Землетрясение Мандока", "Удар в землю, сбивающий весь строй."),
         MasteryTech("taejin_power", "Сила Тэджин Джина", "Мощь, выкованная тренировками Тэджина.")),
    ),
    "speed": (
        (MasteryTech("zack_jab", "Джеб Зака Ли", "Быстрый боксёрский джеб первым в раунде."),
         MasteryTech("jake_step", "Шаг Джейка Кима", "Резкий шаг в сторону и встречный удар."),
         MasteryTech("taekkyeon", "Тхэккён", "Текучие шаги корейского боевого танца.")),
        (MasteryTech("jaegyeon_speed", "Скорость На Джегёна", "Самый быстрый боец своего поколения."),
         MasteryTech("johan_choreo", "Хореография Йохана", "Связки ударов как танец — без пауз."),
         MasteryTech("warren_rush", "Рывок Уоррена Чхэ", "Сокращение дистанции за мгновение.")),
        (MasteryTech("jinyoung_instant", "Мгновение Пак Джинёна", "Скорость за гранью реакции противника."),
         MasteryTech("johan_shadow", "Тень Йохана", "Остаточный образ — удар приходит с другой стороны."),
         MasteryTech("sinu_storm", "Шторм Шину Хана", "Град ударов на высокой скорости.")),
    ),
    "endurance": (
        (MasteryTech("kyokushin_body", "Закалка Кёкушинкай", "Тело, привыкшее к полному контакту."),
         MasteryTech("systema_breath", "Дыхание Системы", "Расслабление и дыхание под ударами."),
         MasteryTech("seokdu_iron", "Железное тело Сокду", "Выдерживает удары, что убивают других.")),
        (MasteryTech("pichon_blood", "Вторая кровь Пичхона", "Второе дыхание, когда силы на исходе."),
         MasteryTech("zack_wind", "Второе дыхание Зака", "Встать после нокдауна и продолжить."),
         MasteryTech("eli_wild", "Дикая живучесть Илая", "Звериная стойкость: чем хуже, тем злее.")),
        (MasteryTech("gapryong_will", "Несгибаемость Гапрёна", "Воля, которую не сломать ничем."),
         MasteryTech("mandeok_wall", "Стена Мандока", "Тело как стена — удары гаснут."),
         MasteryTech("seongji_iron", "Стальная воля Сонджи Юка", "Стоит до последнего, не отступая ни шагу.")),
    ),
    "technique": (
        (MasteryTech("johan_eye", "Взгляд Йохана", "Видит удар — может его повторить."),
         MasteryTech("kim_grips", "Хватки Менеджера Кима", "Захваты и болевые из армейского CQC."),
         MasteryTech("pen_sword", "Меч-ручка Гу Кима", "Любой предмет в руке Гу — клинок.")),
        (MasteryTech("god_eye", "Божий глаз Йохана", "Читает каждое движение противника."),
         MasteryTech("moonlight_sword", "Лунный меч Гу Кима", "Удар, который не успевают увидеть."),
         MasteryTech("warren_jkd", "Джиткундо Уоррена", "Перехват атаки встречным ударом.")),
        (MasteryTech("daniel_copy", "Абсолютное копирование Даниэля", "Чужая техника — твоя после первого взгляда."),
         MasteryTech("goo_four_swords", "Четыре меча Гу Кима", "Высшая форма стиля Гу."),
         MasteryTech("killing_intent", "Жажда убийства Менеджера Кима", "Давление, от которого цепенеет противник.")),
    ),
}
MASTERY_NAMES: dict[str, str] = {"strength": "Сила", "speed": "Скорость", "endurance": "Выносливость", "technique": "Техника"}


def tech_by_code(mastery: str, code: str) -> tuple[int, MasteryTech] | None:
    for tier, techs in enumerate(MASTERY_TREES.get(mastery, ()), 1):
        for t in techs:
            if t.code == code:
                return tier, t
    return None


def tier_cost(tier: int) -> int:
    return MASTERY_TECH_COST_PER_TIER * tier
