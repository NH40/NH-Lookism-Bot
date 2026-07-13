from dataclasses import dataclass


@dataclass(frozen=True)
class FameFragmentDef:
    key: str            # ключ фрагмента внутри сета, напр. "leader"
    name: str
    emoji: str
    description: str    # эффект владения одним этим фрагментом


@dataclass(frozen=True)
class FameSetDef:
    set_key: str
    name: str
    fragments: tuple[FameFragmentDef, ...]
    bonus_name: str
    bonus_description: str
    stub: bool = False   # сет анонсирован, но детали ещё не описаны — кузница его не выдаёт


FAME_SETS: list[FameSetDef] = [
    FameSetDef(
        "gaprena", "Сет Гапрена",
        (
            FameFragmentDef("leader", "Лидер", "🎖", "+50% очков активности (Алея славы)"),
            FameFragmentDef("hero", "Герой", "🦸", "×2 получение статистов из любых источников"),
            FameFragmentDef("romantic", "Романтик", "💘", "×2 к баффам пути Романтика"),
        ),
        "Преодоление",
        "При каждой атаке (все фазы боя, рейд-боссы) получаешь стак «Преодоление» на 20 минут "
        "(до 5 стаков, новая атака обновляет таймер). Каждый стак = +5% доход и боевая мощь (макс. +25%).",
    ),
    FameSetDef(
        "gana", "Сет Гана",
        (
            FameFragmentDef("ui_control", "Контроль ультра инстинкта", "👁", "Даёт Ультра Инстинкт 2 уровня без покупки, пока фрагмент у тебя"),
            FameFragmentDef("monster", "Монстр", "👹", "+60% боевая мощь"),
            FameFragmentDef("path_building", "Построение пути", "🗺", "-50% стоимость крафтов уровня пути и покупки навыков пути"),
        ),
        "Истинный ультра инстинкт",
        "Пока собран весь сет — Ультра Инстинкт в 2 раза эффективнее (тикеты/статисты/тренировки ×2 за авто-тик).",
    ),
    FameSetDef(
        "charles_choi", "Сет Чарльз Чоя",
        (
            FameFragmentDef("ten_geniuses", "Десять гениев", "🧠", "-50% стоимость фрагментов бизнеса, +30% дохода с каждого здания"),
            FameFragmentDef("nhn_group", "NHN Групп", "🏢", "Сетевой эффект: +10% дохода за каждые 10 построенных зданий (макс. +80% на 80 зданиях)"),
            FameFragmentDef("invisible_attacks", "Невидимые атаки", "🥷", "Автоматически мастерство скорости 4 уровня"),
        ),
        "Элита",
        "Пока сет собран хоть у одного игрока в игре — все цены везде +20% для ВСЕХ игроков, кроме владельца сета.",
    ),
    FameSetDef("gite", "Сет Гитэ", (), "—", "Скоро", stub=True),
    FameSetDef("gu", "Сет Гу", (), "—", "Скоро", stub=True),
    FameSetDef("james_lee", "Сет Джеймс Ли", (), "—", "Скоро", stub=True),
]

FAME_SET_MAP: dict[str, FameSetDef] = {s.set_key: s for s in FAME_SETS}

FAME_FORGE_COST = 2000


def fame_fragment_key(set_key: str, frag_key: str) -> str:
    return f"{set_key}:{frag_key}"


def get_fragment_def(set_key: str, frag_key: str) -> FameFragmentDef | None:
    s = FAME_SET_MAP.get(set_key)
    if not s:
        return None
    for f in s.fragments:
        if f.key == frag_key:
            return f
    return None
