"""Публичное API домена district (сервис)."""
from bot.services.district.challenge import (  # noqa: F401
    BotDistrictError,
    ChallengeIssued,
    ChallengeNotFoundError,
    ChallengeOutcome,
    CityAlreadyChallengedError,
    CityNotInCountryError,
    DistrictAlreadyChallengedError,
    NotCityConquerorError,
    NothingToTakeError,
    OutgoingChallengeExistsError,
    accept_challenge,
    issue_challenge,
    issue_city_challenge,
    resolve_expired,
)
from bot.services.district.city import (  # noqa: F401
    CityBotReport,
    CityOwners,
    CityStat,
    CountryMap,
    NoBotsInCityError,
    OwnerGroup,
    attack_city_bots,
    get_city_owners,
    get_country_map,
)
from bot.services.district.district import (  # noqa: F401
    AttackReport,
    BattleOnCooldownError,
    CityConquerorError,
    CityMap,
    DistrictNotFoundError,
    DistrictView,
    EmperorNoConquestError,
    NoAttackersError,
    NotYourCityError,
    OwnDistrictError,
    PlayerDistrictError,
    Territory,
    attack_district,
    get_city_map,
    get_district_view,
    get_influence,
    get_territory,
    seed,
)
from bot.services.district.tom import TomFightResult, fight_tom  # noqa: F401,E402
from bot.services.district.throne import LiberationOutcome, NoThroneTargetError, NotThroneContenderError, ThroneOutcome, ThroneStatus, challenge_throne, promote_or_throne, resolve_liberation, resolve_throne, throne_status  # noqa: F401,E402
from bot.services.district.boss import BossAlreadyDefeatedError, BossFightResult, EventGoneError, fight_boss  # noqa: F401,E402
