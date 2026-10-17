// Типы ответов API экранов «Карта», «Банда» и «Уники» (зеркало pydantic-моделей роутеров
// map/district/boss/gang/recruit/gacha/card).

export interface MapDistrict {
  id: number;
  number: number;
  kind: "mine" | "bot" | "player";
  owner: string | null;
  bot_rank: string | null;
  bot_quantity: number | null;
  bot_power: number | null;
}

export interface MapEvent {
  id: number;
  kind: "boss" | "teacher" | "school";
  code: string;
  title: string;
  subtitle: string | null;
  image: string | null;
  ends_in_seconds: number;
  won: boolean;
  // Учителя: new — задание не взято, active — взято, done — уже открыт.
  state?: "new" | "active" | "done" | null;
  quest_complete?: boolean;
}

export interface MapData {
  city: { id: number; name: string; art: string | null; country_name: string | null; district_count: number };
  emperor: { name: string; tax_percent: number } | null;
  phase: string;
  can_attack: boolean;
  districts: MapDistrict[];
  page: number;
  pages: number;
  total: number;
  mine: number;
  bots: number;
  others: number;
  sole_owner: string | null;
  my_districts: number;
  influence: number;
  income_per_minute: number;
  attack_cooldown_seconds: number;
  boss_cooldown_seconds: number;
  empire: { cities: number; players: number; tax_percent: number; collected: number; holdings: number } | null;
  events: MapEvent[];
}

export interface DistrictCard {
  id: number;
  number: number;
  kind: "mine" | "bot" | "player";
  owner: string | null;
  challenged: boolean;
  bot_rank: string | null;
  bot_quantity: number | null;
  bot_power: number | null;
  attack_quantity: number;
  attack_power: number;
  accept_window_minutes: number;
  can_act: boolean;
  blocked_reason: string | null;
  cooldown_seconds: number;
}

export interface BattleResult {
  message: string;
  journal?: string[];
  won: boolean;
  captured: boolean;
  taken_by_other: boolean;
  district_number: number;
  rounds: number;
  attacker_quantity: number;
  attacker_power: number;
  attacker_dead: number;
  attacker_fled: number;
  attacker_remaining_power: number;
  defender_power: number;
  defender_dead: number;
  influence: number;
  promoted: string | null;
  free_attack: boolean;
  throne: { contender_won: boolean; incumbent: string; rounds: number } | null;
}

export interface ChallengeResult {
  message: string;
  district_number: number;
  defender: string;
  accept_window_minutes: number;
}

export interface BossResult {
  message: string;
  journal?: string[];
  won: boolean;
  boss: string;
  boss_name: string;
  rounds: number;
  attacker_power: number;
  attacker_dead: number;
  boss_power: number;
  boss_remaining_power: number;
  fragments: number;
  fragment_name: string;
}

export interface Squad {
  rank: string;
  stars: number;
  training_level: number;
  school: string | null;
  school_level: number;
  unit_power: number;
  attack: number;
  defense: number;
  total: number;
}

export interface GangData {
  name: string;
  phase: string;
  attack: { quantity: number; power: number };
  defense: { quantity: number; power: number };
  cards_quantity: number;
  squads: Squad[];
  move_percents: number[];
  recruit_cooldown_seconds: number;
  recruit_ceiling_rank: string;
  tickets: { count: number; cap: number; next_in_seconds: number | null };
}

export interface RecruitResult {
  message: string;
  rank: string;
  power: number;
}

export interface UniqueCard {
  code: string;
  name: string;
  rarity: string;
  rarity_label: string;
  power: number;
  image: string | null;
}

export interface RollResult {
  message: string;
  card: UniqueCard;
  skills: { position: string; label: string; skills: { name: string; kind_label: string; text: string }[] }[];
  absolute_perk: string | null;
  copies: number;
  free: boolean;
  tickets: number;
  tickets_cap: number;
}

export interface PositionSkill {
  code: string;
  name: string;
  kind: string;
  kind_label: string;
  text: string;
}

export interface LineupSlot {
  position: string;
  label: string;
  description: string;
  card: UniqueCard | null;
  skills: PositionSkill[];
}

export interface CollectionCard extends UniqueCard {
  attack: number;
  defense: number;
  free: number;
  placed: string[];
  positions: string[];
  skills: Record<string, PositionSkill[]>;
  absolute_perk: string | null;
}

export interface CardsData {
  slots: LineupSlot[];
  collection: CollectionCard[];
  owned_total: number;
  placed_total: number;
  attack_total: number;
  defense_total: number;
  move_percents: number[];
  stylist_pick: string | null;
  stylist_choices: [string, string][];
}

export interface EventCatalogEntry {
  kind: "boss" | "teacher" | "school";
  code: string;
  name: string;
  subtitle: string;
  image: string | null;
  active: boolean;
  ends_in_seconds: number | null;
}

export interface EventsCatalog {
  bosses: EventCatalogEntry[];
  teachers: EventCatalogEntry[];
  schools: EventCatalogEntry[];
}
