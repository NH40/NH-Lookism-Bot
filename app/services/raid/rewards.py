import random
from app.constants.raid import (
    ALCHEMY_MAX_FRAGMENTS_PER_RAID,
    PATH_FRAGMENTS_MAX_PER_RAID,
    BUSINESS_FRAGMENTS_MAX_PER_RAID,
)


def calc_fragments(
    damage: int,
    boss_hp: int,
    reward_type: str = "ui",
    drop_bonus_pct: int = 0,
) -> int:
    ratio = min(1.0, damage / boss_hp)
    if reward_type == "alchemy":
        if ratio >= 0.5:
            base = random.randint(25, ALCHEMY_MAX_FRAGMENTS_PER_RAID)
        elif ratio >= 0.2:
            base = random.randint(15, 24)
        elif ratio >= 0.05:
            base = random.randint(8, 14)
        else:
            base = random.randint(3, 7)
    elif reward_type == "path":
        if ratio >= 0.5:
            base = random.randint(20, PATH_FRAGMENTS_MAX_PER_RAID)
        elif ratio >= 0.2:
            base = random.randint(12, 19)
        elif ratio >= 0.05:
            base = random.randint(5, 11)
        else:
            base = random.randint(2, 4)
    elif reward_type == "business":
        if ratio >= 0.5:
            base = random.randint(15, BUSINESS_FRAGMENTS_MAX_PER_RAID)
        elif ratio >= 0.2:
            base = random.randint(9, 14)
        elif ratio >= 0.05:
            base = random.randint(4, 8)
        else:
            base = random.randint(2, 3)
    else:
        if ratio >= 0.5:
            base = random.randint(20, 35)
        elif ratio >= 0.2:
            base = random.randint(12, 19)
        elif ratio >= 0.05:
            base = random.randint(5, 11)
        else:
            base = random.randint(2, 4)
    return int(base * (1 + drop_bonus_pct / 100))


def distribute_reward(user, reward_type: str, fragments: int) -> int:
    """Apply fragment reward to the user and return the new total."""
    if reward_type == "alchemy":
        user.alchemy_fragments += fragments
        return user.alchemy_fragments
    elif reward_type == "path":
        user.path_fragments += fragments
        return user.path_fragments
    elif reward_type == "business":
        user.business_fragments = getattr(user, "business_fragments", 0) + fragments
        return user.business_fragments
    else:
        user.ui_fragments += fragments
        return user.ui_fragments
