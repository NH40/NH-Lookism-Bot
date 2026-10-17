// Типы ответов GET /api/development и GET /api/training (см. api/routers/development.py, training.py).

export type DevTab = "path" | "techniques" | "genius" | "blood" | "awakening";

export interface DevTask {
  label: string;
  done: number;
  need: number;
}

export interface DevQuest {
  ref: string;
  title: string;
  tasks: DevTask[];
  complete: boolean;
}

export interface DevLevel {
  n: number;
  text: string;
  state: "done" | "bought" | "next" | "locked";
}

export interface DevItem {
  code: string;
  name: string;
  theme: string;
  level: number;
  floor: number;
  next_cost: number | null;
  levels: DevLevel[];
}

export interface TrainingStatus {
  personal_left: number;
  extras_left: number;
}

export interface DevelopmentResponse<T> {
  tab: DevTab;
  training: TrainingStatus;
  max_level: number;
  data: T;
}

export interface PathData {
  stage: number;
  rank_sum: number;
  rank_needed: number;
  conviction_quest: DevQuest | null;
  fragments: number;
  awaken_cost: number;
  points: number;
  swap_cooldown: number;
  active: string | null;
  active2: string | null;
  second_body: boolean;
  next_cost: number | null;
  next_cost2: number | null;
  owned: DevItem[];
  bought: { code: string; name: string }[];
  training_kpd: number;
  training_kpd_cap: number;
}

export interface TechniquesData {
  active: string | null;
  fragments: number;
  swap_cooldown: number;
  owned: DevItem[];
  quests: (DevQuest & { code: string })[];
}

export interface GeniusData {
  active: string | null;
  fragments: number;
  coins: number;
  swap_cooldown: number;
  owned: DevItem[];
  roll_fragments: number;
  roll_coins: number;
  total: number;
}

export interface BloodOption {
  code: string;
  name: string;
  description: string;
  first: string;
}

export interface BloodData {
  chosen: boolean;
  options?: BloodOption[];
  blood_drops?: number;
  first?: DevItem;
  second_body?: boolean;
  second?: DevItem | null;
  options2?: { code: string; name: string }[];
}

export interface AwakeningLevel {
  n: number;
  mult: number;
  text: string;
  state: "done" | "next" | "locked";
}

export interface AwakeningData {
  level: number;
  max: number;
  multiplier: number;
  next_multiplier: number;
  is_emperor: boolean;
  maxed: boolean;
  ready: boolean;
  next_floor: string;
  next_blood: number;
  quest: DevQuest | null;
  levels: AwakeningLevel[];
  confirm_seconds: number;
}

export interface TrainingResponse {
  personal: {
    left: number;
    total: number;
    min_points: number;
    max_points: number;
    nothing_percent: number;
    potential: string;
    dev_points: number;
  };
  extras: {
    left: number;
    total: number;
    coverage_percent: number;
    stages: { n: number; label: string; percent: number }[];
    gym_bonus: number;
    has_extras: boolean;
  };
  last_extras: { attempted: number; stage1: number; stage2: number; stage3: number } | null;
  techniques: {
    items: {
      code: string;
      name: string;
      teacher: string;
      level: number;
      next_level: number | null;
      stage: "pay" | "quest" | "level" | "max";
      price: number;
      fragments_cost: number;
      tasks: { label: string; done: number; need: number }[];
    }[];
    fragments: number;
    coins: number;
  } | null;
  schools: {
    code: string; teacher: string; school: string; effect: string; state: "owned" | "unlocked" | "locked"; cooldown: number;
    quest: DevQuest | null; price: number;
  }[];
  school_lesson_price: number;
}

export interface ExtrasResult {
  message: string;
  attempted: number;
  stage1: number;
  stage2: number;
  stage3: number;
}

export interface MasteryData {
  tiers: { code: string; label: string; tier: number; tier_label: string; effect: string; can_invest: boolean }[];
  status: "pending" | "active" | "trainer" | "complete" | null;
  stage: number;
  stages: number;
  stage_name: string;
  tasks: { label: string; progress: number; target: number; done: boolean; locked: boolean }[];
  tom_power: number;
  tom_unlocked: boolean;
  points_bought: number;
  points_free: number;
  points_per_stage: number;
  price: number | null;
  available_in_seconds: number | null;
  nh_coins: number;
  battle_cooldown_seconds: number;
}
