// Типы экрана «Магазин»: контракты, зелья, ячейки, вклады (GET /api/shop).
export interface ShopRank {
  rank: string;
  unit_price: number;
  power: number;
}

export interface ShopContractActive {
  rank: string;
  quantity: number;
  expires_in_seconds: number;
}

export interface ShopContracts {
  ceiling: string;
  hours: number;
  discount: number;
  max_quantity: number;
  ranks: ShopRank[];
  active: ShopContractActive[];
}

export interface ShopTier {
  tier: number;
  price: number;
  unlocked: boolean;
  effect: string;
}

export interface ShopPotion {
  kind: string;
  name: string;
  about: string;
  minutes: number;
  tiers: ShopTier[];
  active_tier: number;
  left_seconds: number;
  auto_tier: number;
}

export interface ShopPotions {
  max_tier: number;
  auto_slots: number;
  discount: number;
  potions: ShopPotion[];
}

export interface ShopCell {
  slot: number;
  opened: boolean;
  kind: "" | "res" | "statist";
  code: string;
  label: string;
  amount: number;
  debt: number;
  open_cost: number;
  next_to_open: boolean;
}

export interface ShopStoreResource {
  code: string;
  name: string;
  have: number;
}

export interface ShopStoreSquad {
  code: string;
  label: string;
  have: number;
}

export interface ShopStorage {
  fee_per_hour: number;
  debt_cap_hours: number;
  cells: ShopCell[];
  resources: ShopStoreResource[];
  squads: ShopStoreSquad[];
}

export interface ShopDeposit {
  id: number;
  resource: string;
  name: string;
  amount: number;
  payout: number;
  rate: number;
  hours: number;
  left_seconds: number;
  ready: boolean;
}

export interface ShopDepositResource {
  code: string;
  name: string;
  cap: number;
  have: number;
  rates: Record<string, number>;
}

export interface ShopDeposits {
  max_active: number;
  terms: number[];
  resources: ShopDepositResource[];
  deposits: ShopDeposit[];
}

export interface ShopData {
  nh_coins: number;
  pending: number;
  contracts: ShopContracts;
  potions: ShopPotions;
  storage: ShopStorage;
  deposits: ShopDeposits;
}
