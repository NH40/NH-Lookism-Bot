// Типы ответов экранов «Профиль» и «Ещё» (src/api/routers/profile.py).
export interface ProfileStat {
  code: string;
  label: string;
  rank: string;
}

export interface ProfileDevItem {
  label: string;
  level: number;
  kind: "bloodline" | "path" | "technique" | "genius";
}

export interface ProfileData {
  user_id: number;
  username: string | null;
  display_name: string | null;
  country: { code: string; name: string } | null;
  city: { id: number; name: string; district_count: number } | null;
  phase: string;
  phase_label: string;
  potential_label: string;
  potential_points?: number;
  potential_cost?: number | null;
  potential_next?: string | null;
  gang_name: string | null;
  army_power: number;
  attack_power: number;
  defense_power: number;
  districts: number;
  influence: number;
  nh_coins: number;
  nh_coins_pending: number;
  donate_balance: number;
  tickets: number;
  tickets_cap: number;
  online: number;
  avatar: string | null;
  stats: ProfileStat[];
  dev_points: number;
  phase_progress: { target_label: string; scope_label: string; current: number; total: number } | null;
  development: ProfileDevItem[];
  second_body: boolean;
  potions: ProfilePotion[];
  absolutes: { items: { code: string; name: string; perk: string; via_stylist: boolean }[]; blocked_seconds: number } | null;
  clan_name: string | null;
}

export interface MoreData {
  clan: {
    name: string;
    members: number;
    max_members: number;
    donate_level: number;
    max_donate_level: number;
    lands: number;
    power: number;
  } | null;
  donate_balance: number;
  income_per_minute: number;
  income_pending: number;
  is_admin?: boolean;  // плитка «Админ-панель» — только сотрудникам
  bot_link: string | null;
}

export interface ProfilePotion {
  name: string;
  tier: string;
  left_seconds: number;
  effect: string;
}
