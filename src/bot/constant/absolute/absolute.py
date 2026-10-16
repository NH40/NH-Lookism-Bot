"""Абсолютные карты — константы (коды карт; перки — `config/absolute`)."""
from __future__ import annotations

ABS_HASBULLA = "hasbulla_horse"
ABS_KUROPATKA = "kuropatkaa_hopeful"
ABS_MARISE = "marise_boosty"
ABS_TABASKO = "tabasko_unlucky"
ABS_OGURCHIK = "malosolny_ogurchik_emperor"
ABS_QUANDE = "quande_manchester_100m"
ABS_MANAGER = "manager_fair"
ABS_NIKITA = "nikita_despair"
ABS_ARKHANGEL = "arkhangel_wwip"
ABS_STYLIST = "some_thing_stylist"
ABS_ARIAN = "arian_absolute"

ABSOLUTES: tuple[str, ...] = (
    ABS_HASBULLA, ABS_KUROPATKA, ABS_MARISE, ABS_TABASKO, ABS_OGURCHIK, ABS_QUANDE, ABS_MANAGER, ABS_NIKITA,
    ABS_ARKHANGEL, ABS_STYLIST, ABS_ARIAN,
)
# Перки, которые может выбрать Стилист (его собственный — нет; у Quan'de перка нет — решение пользователя).
STYLIST_CHOICES: tuple[str, ...] = tuple(c for c in ABSOLUTES if c not in (ABS_STYLIST, ABS_QUANDE))

CB_STYLIST_PICK_PREFIX = "abs:style:"
"""f"{CB_STYLIST_PICK_PREFIX}{card_code}" — Стилист выбирает перк абсолюта."""
