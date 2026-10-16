// Типы экрана «Казино» (GET /api/casino, покерный стол — /api/casino/poker/table/{id}).
export interface CasinoResource {
  code: string;
  label: string;
  balance: number;
}

export interface CasinoSquad {
  code: string;
  label: string;
  total: number;
}

export interface CasinoSymbol {
  symbol: string;
  multiplier: number;
}

export interface PlayingCardData {
  rank: string;
  suit: string;
  hidden: boolean;
}

export interface BlackjackHand {
  player: PlayingCardData[];
  dealer: PlayingCardData[];
  player_total: number;
  dealer_total: number | null;
  stake_label: string;
  doubled: boolean;
  finished: boolean;
  can_double: boolean;
  outcome: string;
  payout: number;
  message: string;
}

export interface PokerLobbyRow {
  id: number;
  buy_in: number;
  players: number;
  max_players: number;
  starts_in: number;
}

export interface PokerConfig {
  buy_ins: number[];
  max_players_min: number;
  max_players_max: number;
  wait_options: number[];
  rake_percent: number;
  action_timeout: number;
}

export interface CasinoData {
  resources: CasinoResource[];
  squads: CasinoSquad[];
  symbols: CasinoSymbol[];
  pair_multiplier: number;
  statists_min: number;
  blackjack: BlackjackHand | null;
  lobby: PokerLobbyRow[];
  seat_table_id: number | null;
  poker: PokerConfig;
  coins: number;
}

export interface SlotsResult {
  message: string;
  reel: string[];
  outcome: "triple" | "pair" | "loss";
  payout: number;
}

export interface PokerSeat {
  seat: number;
  name: string;
  stack: number;
  round_bet: number;
  folded: boolean;
  all_in: boolean;
  leaving: boolean;
  dealer: boolean;
  turn: boolean;
  me: boolean;
}

export interface PokerTable {
  id: number;
  status: "waiting" | "active" | "closed";
  hand_no: number;
  street: string;
  buy_in: number;
  small_blind: number;
  big_blind: number;
  max_players: number;
  pot: number;
  starts_in: number;
  board: PlayingCardData[];
  hole: PlayingCardData[];
  seats: PokerSeat[];
  my_turn: boolean;
  to_call: number;
  min_raise_to: number;
  all_in_to: number;
  can_raise: boolean;
  seconds_left: number;
}
