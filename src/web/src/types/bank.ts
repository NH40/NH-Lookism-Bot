// Банки игроков и кредиты (`/api/bank`) и родословная Пеньгуана (`/api/penguan`).

export interface BankRow {
  id: number;
  owner: string;
  capital: number;
  fixed_rate: number | null;
  hourly_rate: number | null;
  penalty_rate: number;
  min_days: number;
  max_days: number;
  open_loans: number;
}

export interface LoanRow {
  id: number;
  name: string;
  status: "pending" | "offered" | "active" | "frozen" | "slave" | string;
  kind: "fixed" | "hourly" | "daily" | string;
  rate: number;
  penalty_rate: number;
  amount: number;
  debt: number;
  principal: number;
  interest: number;
  penalty: number;
  paid: number;
  days: number;
  terms: string | null;
  due_in: number;
  frozen_in: number;
  offer_in: number;
}

export interface BankTeam {
  is_owner: boolean;
  owner: string;
  capital: number;
  lent: number;
  reserved: number;
  open_loans: number;
  fixed_rate: number | null;
  hourly_rate: number | null;
  penalty_rate: number;
  min_days: number;
  max_days: number;
  earned: number;
  members: { id: number; name: string }[];
  apps: LoanRow[];
  loans: LoanRow[];
}

export interface BankHome {
  banks: BankRow[];
  more: boolean;
  page: number;
  loans: LoanRow[];
  team: BankTeam | null;
  coins: number;
  frozen: boolean;
  limits: {
    fixed_min: number; fixed_max: number; hourly_min: number; hourly_max: number; penalty_max: number; days_min: number; days_max: number;
    min_capital: number; min_loan: number; freeze_days: number; slave_share: number; members_max: number;
  };
}

export interface PenguanBuff {
  kind: string;
  name: string;
  effect: string;
  price: number;
  active_in: number;
}

export interface PenguanData {
  active: boolean;
  income: number;
  districts: number;
  cities: number;
  points: number;
  points_cap: number;
  bonuses: string[];
  buffs: PenguanBuff[];
  buyback: { units: number; power: number; price: number } | null;
  buyout: { price: number; cooldown: number } | null;
  builder: boolean;
}

export interface PenguanBuilder {
  rank: string;
  ceiling: string;
  level: number;
  level_cap: number;
  stars: number;
  school: string;
  school_label: string;
  school_level: number;
  unit_power: number;
  unit_price: number;
  bought_today: number;
  daily_cap: number;
  max_units: number;
  presets: number[];
}
