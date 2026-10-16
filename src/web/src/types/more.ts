// Типы подэкранов раздела «Ещё»: бизнес, донат, чёрный рынок, клан, настройки.
export interface BusinessData {
  nh_coins: number;
  pending: number;
  per_minute: number;
  storage_full_in_seconds: number;
  level: number;
  capacity: number;
  capacity_per_district: number;
  level_cost: number | null;
  capacity_cost: number | null;
  tax_percent: number | null;
  districts: number;
  buildings: { code: string; name: string; count: number }[];
  gym_bonus_percent: number;
  parliament_influence: number;
  max_upgrade: number;
  district_list: BusinessDistrict[];
  catalog: BusinessCatalogItem[];
}

export interface BusinessDistrict {
  id: number;
  city: string;
  number: number;
  used: number;
  capacity: number;
  free: number;
  buildings: { code: string; name: string; count: number }[];
}

export interface BusinessCatalogItem {
  code: string;
  name: string;
  description: string;
  cost: number;
  free_first: boolean;
}

export interface DonateData {
  balance: number;
  presets: number[];
  min_rub: number;
  max_rub: number;
  payments_enabled: boolean;
}

export interface MarketItem {
  code: string;
  name: string;
  level: number;
  next_price: number | null;
}

export interface MarketKind {
  kind: string;
  label: string;
  hint: string;
  items: MarketItem[];
}

export interface MarketData {
  balance: number;
  max_level: number;
  second_body_owned: boolean;
  second_body_price: number;
  battle_pass_premium: boolean;
  battle_pass_price: number;
  kinds: MarketKind[];
}

export interface SettingsData {
  categories: { code: string; label: string; enabled: boolean }[];
}

export interface TopPlayer {
  place: number;
  user_id: number;
  name: string;
  phase: string;
  power: number;
  clan: string | null;
  reward: string;
  is_me: boolean;
}

export interface TopData {
  players: TopPlayer[];
  clans: { place: number; name: string; lands: number; members: number; reward: string }[];
  my_place: number | null;
  my_power: number;
  season_ends_in: number | null;
}

export interface PlayersData {
  players: TopPlayer[];
  page: number;
  pages: number;
  total: number;
}
