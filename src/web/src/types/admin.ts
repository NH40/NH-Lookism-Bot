// Типы админ-панели Mini App (`/api/admin*`, см. api/routers/admin*.py).
export interface Named {
  code: string;
  name: string;
}

export interface AdminMeta {
  role: string;
  role_name: string;
  is_super: boolean;
  sections: { code: string; title: string }[];
  player_rights: { give: boolean; dev: boolean; punish: boolean; logs: boolean };
  catalog: {
    resources: Named[];
    ranks: string[];
    dev_kinds: { kind: string; title: string; items: Named[] }[];
    bloodlines: Named[];
    potentials: string[];
    stats: Named[];
    max_level: number;
    awakening_max: number;
    phases: Named[];
    ban_durations: Named[];
    ban_reason_max: number;
    statist_take_percents: number[];
    statist_add_amounts: number[];
    statist_give_amounts: number[];
    mass_filters: Named[];
    mass_max_amount: number;
    config_durations: { hours: number; name: string }[];
    ref_name_max: number;
    roles: Named[];
    event_kinds: { key: string; title: string; items: { idx: number; name: string }[] }[];
  };
}

export interface AdminDevLevel {
  code: string;
  name: string;
  level: number;
  active: boolean;
  active2: boolean;
}

export interface AdminPlayerCard {
  id: number;
  name: string;
  username: string | null;
  role: string | null;
  role_name: string | null;
  banned: boolean;
  ban_forever: boolean;
  banned_until: string | null;
  ban_reason: string | null;
  phase: string;
  phase_name: string;
  gang: string | null;
  city: string | null;
  districts: number;
  clan: string | null;
  last_active_at: string | null;
  created_at: string | null;
  resources: { code: string; name: string; amount: number; label: string }[];
  bloodline: { code: string; name: string; level: number } | null;
  bloodline2: { code: string; name: string; level: number } | null;
  paths: AdminDevLevel[];
  techniques: AdminDevLevel[];
  geniuses: AdminDevLevel[];
  awakening: number;
  potential: string | null;
  second_body: boolean;
  stats: Record<string, string>;
  bp_level: number;
  bp_premium: boolean;
  donated_rub: number;
  donate_unlocks: number;
}

export interface AdminGiveData {
  name: string;
  resources: { code: string; name: string; amount: number; label: string }[];
  scrolls: number;
  bp_xp: number;
  cards: Named[];
}

export interface AdminStatists {
  name: string;
  total: number;
  attack: number;
  defense: number;
  squads: { key: string; title: string; total: number; attack: number; defense: number }[];
}

export interface AdminDev {
  name: string;
  systems: Record<string, { owned: Record<string, number>; active: string | null }>;
  bloodlines: Record<string, { code: string | null; level: number }>;
  second_body: boolean;
  premium: boolean;
  awakening: number;
  potential: string | null;
  stats: Record<string, string>;
  phase: string;
}

export interface AdminQuests {
  name: string;
  daily: { slot: number; title: string; progress: number; target: number }[];
  dev: { id: number; title: string }[];
}

export interface Paged<T> {
  rows: T[];
  total: number;
  per_page: number;
}

export interface AuditRow {
  id: number;
  admin_id: number;
  action: string;
  target_id: number | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface AdminSystem {
  beta: { code: string; allowed: number } | null;
  tech: boolean;
}

export interface AdminConfigKey {
  key: string;
  title: string;
  value: number;
  default: number;
  min: number;
  max: number;
  integer: boolean;
  expiring: boolean;
  overridden: boolean;
  left_seconds: number | null;
}

export interface AdminPromo {
  id: number;
  code: string;
  reward: { code: string; amount: number; label: string }[];
  max_uses: number | null;
  used: number;
  expires_at: string | null;
  users: string[] | null;
  active: boolean;
  alive: boolean;
  created_at: string;
}

export interface AdminReferral {
  id: number;
  name: string;
  code: string;
  visits: number;
  link: string;
  created_at: string;
  stats: Record<string, number>;
}

export interface AdminEvent {
  id: number;
  kind: string;
  kind_name: string;
  title: string;
  left_seconds: number;
  clan_id: number | null;
  entries: number;
}

export interface AdminCity {
  id: number;
  name: string;
  country: string;
  emperor: { id: number; label: string } | null;
  pending_challenges: number;
  pending_wars: number;
  districts: { id: number; number: number; owner_id: number | null; owner: string | null; challenge: { attacker_id: number; defender_id: number } | null }[];
}

export interface AdminClan {
  id: number;
  name: string;
  owner_id: number;
  owner: string;
  lands: number;
  treasury: number;
  donate_level: number;
  power: number;
  shield_seconds: number;
  cooldown_seconds: number;
  buyers: number;
  paid: number;
  members: { id: number; rank: string; label: string }[];
  limits: { lands_min: number; lands_max: number; donate_max: number };
}

export interface AdminSeason {
  number: number;
  starts_at: string;
  ends_at: string;
  premium: number;
  left_seconds: number;
}

export interface AdminSeasonPlayer {
  id: number;
  label: string;
  xp: number;
  level: number;
  premium: boolean;
  claimed_free: number;
  claimed_premium: number;
  quests: { slot: number; task: string; progress: number; target: number; xp: number; done: boolean }[];
}
