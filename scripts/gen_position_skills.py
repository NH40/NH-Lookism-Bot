"""Раскладка навыков позиций по картам → `src/bot/config/position_skill/card_skills.py`.

Подбор детерминированный: канонные черты персонажа (`FAMILY_TAGS`) × теги навыков позиции,
редкость задаёт число навыков (`SKILL_COUNT`) и доступные tier (`TIER_MIN_RARITY`). Старшие
редкости выбирают первыми, повтор навыка штрафуется (так покрыт весь каталог). Канонные
«подписи» (`SIGNATURES`) достаются персонажу при любой редкости.

Результат коммитится: навыки карты не должны тихо меняться после релиза. Перегенерировать —
только осознанно (новые карты, правка каталога): `python scripts/gen_position_skills.py`.
"""
from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "src" / "bot" / "config" / "position_skill" / "card_skills.py"

from bot.config.card.cards_data import CARDS  # noqa: E402
from bot.config.position_skill.position_skill import POOLS, SKILL_COUNT, TIER_MIN_RARITY  # noqa: E402
from bot.constant.card import RARITY_ORDER  # noqa: E402

FAMILY_TAGS = {
    # Первое поколение и вершины
    "Gapryong": "leader power endurance", "Old Gapryong": "leader endurance power",
    "Shingen": "power dark leader rage", "James": "leader speed tech discipline", "Gitae": "power dark chaos rage",
    "Mujin": "tech defense endurance discipline", "Jinyoung": "tech money info support",
    "Daniel": "copy tech speed leader", "OG Daniel": "copy speed tech", "Big Daniel": "copy power endurance",
    # Новые легенды и легенды
    "Gun": "power dark weapon tech", "Goo": "weapon tech chaos speed", "Johan": "info copy tech",
    "Tom": "rage power speed", "Jake": "leader power endurance", "Samuel": "dark power rage leader",
    "Jincheol": "dark info", "Sophia": "info dark defense", "Samdak": "power rage", "Manager Kim": "defense discipline support",
    "Hansu": "power weapon", "Brekdak": "defense endurance power",
    # Нулевое поколение
    "Baekho": "defense power endurance", "Elite": "leader money discipline", "Shintaro": "weapon speed tech",
    "Paecheon": "power rage dark", "Eunha": "tech speed", "Gentleman": "support leader discipline",
    "Choi": "speed tech", "Shigeaki": "info dark", "Hiroaki": "dark info", "Jaesu": "power", "Bangho": "power speed",
    "Beolgu": "defense endurance", "Gwang": "power rage", "Bakgu": "power endurance", "Yoru Park": "info defense dark",
    "Somi": "money defense support",
    # Сильные короли
    "Jinrang": "leader power endurance", "Seongji": "tech power", "Changsu": "power", "J": "info defense discipline",
    "Jaegyeon": "speed tech", "Yujae": "dark info", "Yugang": "leader power", "Jinchang": "power leader",
    "Ryu": "dark", "Mugak": "dark power", "Lineman": "defense discipline", "Zack": "tech speed",
    "Eli": "leader rage speed", "Mandeok": "defense endurance", "Ryuhei": "dark tech", "Yuseong": "defense endurance",
    # Короли
    "Dalyoung": "leader discipline", "NO 1": "power", "Gongseob": "speed power", "Sang": "leader discipline power",
    "Taesoo": "power", "Taehun": "discipline defense info", "Sinu": "tech speed", "Seokdu": "defense endurance",
    "Taejin": "tech power", "Vin Jin": "tech speed", "Vasco": "power endurance leader defense", "Jay": "weapon defense tech",
    "Warren": "tech power", "Jerry": "power", "Jungseok": "discipline power", "Baekjin": "discipline tech",
    "Jaegwang": "discipline power", "Hashik": "discipline", "BJ Showby": "money info", "Junyuk": "leader", "Jaemin": "leader",
    # Главы группировок и члены банды
    "Kenta": "power dark", "Hudson": "tech", "Olli": "defense", "Jihan": "speed power", "Jibeom": "power",
    "Xiaolung": "weapon tech", "Mitsuki": "info", "Arim": "power", "Jihoon": "power", "Sangjin": "power defense",
    "Crystal": "money", "Mary": "tech defense", "Sally Park": "money support", "Logan": "dark", "Roy": "speed",
    "Sung": "speed", "Yeowool": "speed", "Boknam": "speed power", "Sebastian": "speed power", "Mira": "info", "Zoe": "defense",
    # Абсолюты — кастомные карты игроков
    "Marise": "money support", "Малосольный Огурчик": "leader money",
}

# Ручные «подписи» канона: навык, который у карты будет всегда, если доступен по позиции/редкости.
SIGNATURES = {
    "gapryong_prime": {"leader": ["overcoming", "king_of_all"]}, "james_prime": {"leader": ["seoul_king"]},
    "shingen_prime": {"warlord": ["war_god"]}, "johan_path": {"scout": ["god_eye"]}, "johan_eye_drops": {"scout": ["god_eye"]},
    "tom_rage_mode": {"warlord": ["rage", "madness"]}, "gun_tui": {"warlord": ["destroyer"]},
    "goo_50_styles": {"tactician": ["adaptation", "tactical_genius"]}, "daniel_prime": {"tactician": ["adaptation"]},
    "big_daniel_ui": {"tactician": ["adaptation"]}, "manager_kim_path": {"security": ["impenetrable"]},
    "sophia_path": {"scout": ["god_eye"], "security": ["disinformation"]}, "jincheol_path": {"spy": ["puppeteer"]},
    "gitae_path": {"spy": ["kings_shadow"]}, "jinyoung_path": {"businessman": ["money_king"]},
    "mujin_prime": {"defender": ["unbreakable"]}, "brekdak_legend": {"defender": ["bastion"]},
}



def family(name: str) -> str:
    base = re.sub(r"\s*\(.*\)$", "", name).strip()
    return base if base in FAMILY_TAGS else base.split()[0]


def _h(*parts: str) -> float:
    return int(hashlib.md5("|".join(parts).encode()).hexdigest()[:6], 16) / 0xFFFFFF


def assign() -> tuple[dict[str, dict[str, list[str]]], Counter]:
    usage: Counter = Counter()
    out: dict[str, dict[str, list[str]]] = {}
    top_r: dict[str, int] = {}
    for c in CARDS:
        for pos in c.positions:
            top_r[pos] = max(top_r.get(pos, 0), min(RARITY_ORDER.index(c.rarity), 7))
    for c in sorted(CARDS, key=lambda c: -RARITY_ORDER.index(c.rarity)):
        r = RARITY_ORDER.index(c.rarity)
        tags = set(FAMILY_TAGS.get(family(c.name), "").split())
        out[c.code] = {}
        for pos in c.positions:
            pool = [s for s in POOLS[pos] if min(TIER_MIN_RARITY[s.tier], top_r[pos]) <= r]
            picked = [s for s in SIGNATURES.get(c.code, {}).get(pos, []) if any(p.code == s for p in POOLS[pos])]

            def score(s, code=c.code, pos=pos, tags=tags):
                return 3 * len(tags & set(s.tags)) + 1.5 * s.tier - 2.5 * usage[(pos, s.code)] + _h(code, pos, s.code)

            for s in sorted(pool, key=score, reverse=True):
                if len(picked) >= SKILL_COUNT[r]:
                    break
                if s.code not in picked:
                    picked.append(s.code)
            for s in picked:
                usage[(pos, s)] += 1
            out[c.code][pos] = picked
    return out, usage


def main() -> None:
    result, usage = assign()
    unused = [(p, s.code) for p, pool in POOLS.items() for s in pool if not usage[(p, s.code)]]
    lines = [
        '"""СГЕНЕРИРОВАНО `scripts/gen_position_skills.py` — не править руками.',
        "",
        "Навыки позиций каждой карты: код карты → позиция → коды навыков (порядок = важность).",
        '"""',
        "from __future__ import annotations",
        "",
        "CARD_SKILLS: dict[str, dict[str, tuple[str, ...]]] = {",
    ]
    for c in CARDS:
        if not result.get(c.code):
            continue
        parts = ", ".join(f"{pos!r}: ({', '.join(repr(s) for s in skills)},)" for pos, skills in result[c.code].items())
        lines.append(f"    {c.code!r}: {{{parts}}},")
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written {OUT} · cards {len(result)} · unused skills: {unused or 'none'}")


if __name__ == "__main__":
    main()
