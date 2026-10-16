export interface QuestItem {
  slot: number
  task: string
  label: string
  tier: number
  xp: number
  progress: number
  target: number
  done: boolean
}

export interface QuestsData {
  quests: QuestItem[]
  completed: number
  total: number
  next_multiplier: number
  full_reroll_available: boolean
  swaps_left: number
  is_admin: boolean
  swaps_per_day: number
  resets_in: number
  scrolls: number
  skippable: { id: number; label: string }[]
}

export type PassTrack = "free" | "prem"

export interface RewardItem {
  code: string
  amount: number
}

export interface PassEntry {
  level: number
  free: RewardItem[]
  premium: RewardItem[]
  free_claimed: boolean
  premium_claimed: boolean
}

export interface PassData {
  season_number: number
  season_left: number
  level: number
  xp_in_level: number
  level_xp: number
  loop_position: number
  is_premium: boolean
  premium_price: number
  claimed_free: number
  claimed_premium: number
  free_claimable: boolean
  premium_claimable: boolean
  page: number
  pages_max: number
  boost: { multiplier: number; used: number; cap: number; resets_in: number }
  scrolls: number
  entries: PassEntry[]
}
