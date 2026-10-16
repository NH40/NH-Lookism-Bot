// Характеристики (API `/api/stats`).

export interface StatItem {
  code: string;
  label: string;
  rank: string;
  effect: string;
  next_cost: number | null;
}

export interface StatsData {
  stats: StatItem[];
  potential: string;
  dev_points: number;
  strength_power_percent: number;
  modes: string[];
}
