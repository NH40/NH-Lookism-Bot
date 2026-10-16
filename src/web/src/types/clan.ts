// Типы ответов /api/clan (src/api/routers/clan.py).

export interface ClanCard {
  clan_id: number;
  name: string;
  members: number;
  max_members: number;
  lands: number;
  donate_level: number;
  top10: boolean;
  applied: boolean;
}

export interface ClanBrowse {
  items: ClanCard[];
  page: number;
  pages: number;
  total: number;
}

export interface ClanInviteRef {
  clan_id: number;
  name: string;
}

export interface ClanNone {
  coins: number;
  create_cost: number;
  name_min: number;
  name_max: number;
  application: ClanInviteRef | null;
  invites: ClanInviteRef[];
  browse: ClanBrowse;
}

export interface ClanMember {
  user_id: number;
  name: string;
  username: string | null;
  rank: string;
  rank_label: string;
  is_me: boolean;
  can_kick: boolean;
  can_rank: boolean;
  garrison_access: boolean;
  can_access: boolean;
}

export interface ClanPerson {
  user_id: number;
  name: string;
  username: string | null;
}

export interface ClanCan {
  manage: boolean;
  kick: boolean;
  set_rank: boolean;
  transfer: boolean;
  leave: boolean;
}

export interface ClanInfo {
  clan_id: number;
  name: string;
  description: string | null;
  members: ClanMember[];
  max_members: number;
  lands: number;
  max_lands: number;
  treasury: number;
  donate_level: number;
  max_donate_level: number;
  next_donate_price: number | null;
  donate_buyers: string[];
  power: number;
  requests: ClanPerson[];
  access_requests: ClanPerson[];
  set_ranks: { rank: string; label: string }[];
}

export interface ClanData {
  clan: ClanInfo | null;
  my_rank: string | null;
  my_rank_label: string | null;
  can: ClanCan | null;
  coins: number;
  donate_coins: number;
  no_clan: ClanNone | null;
}

export interface ClanBuilding {
  kind: string;
  name: string;
  about: string;
  count: number;
  max: number;
  next_price: number | null;
  refund: number;
}

export interface ClanLands {
  lands: number;
  max_lands: number;
  used: number;
  free: number;
  treasury: number;
  next_land_price: number | null;
  buildings: ClanBuilding[];
  coins: number;
  donate_level: number;
  max_donate_level: number;
  next_donate_price: number | null;
  donate_coins: number;
  donate_buyers: string[];
}

export interface ClanStatist {
  key: string;
  title: string;
  quantity: number;
  power: number;
}

export interface ClanGarrisonCard {
  code: string;
  name: string;
  quantity: number;
  power: number;
  image: string | null;
}

export interface ClanGarrison {
  contracts: { rank: string; quantity: number; power: number; left_seconds: number }[];
  power: number;
  statists: ClanStatist[];
  cards: ClanGarrisonCard[];
  can_take: boolean;
  take_in_seconds: number;
  needs_approval: boolean;
  pending: boolean;
  my_statists: ClanStatist[];
  my_cards: ClanGarrisonCard[];
}

export interface ClanWarTarget {
  clan_id: number;
  name: string;
  lands: number;
  members: number;
  shielded: boolean;
}

export interface ClanWarRow {
  attacker: string;
  defender: string;
  won_by_me: boolean;
  i_attacked: boolean;
  lands_taken: number;
  treasury_taken: number;
  created_at: string;
}

export interface ClanWar {
  targets: ClanWarTarget[];
  page: number;
  pages: number;
  cooldown_seconds: number;
  shield_seconds: number;
  power: number;
  can_attack: boolean;
  history: ClanWarRow[];
}

export interface ClanAttackResult {
  message: string;
  won: boolean;
  rounds: number;
  attacker_power: number;
  defender_power: number;
  attacker_dead: number;
  defender_dead: number;
  lands_taken: number;
  lands_gained: number;
  treasury_taken: number;
  defender_name: string;
}
