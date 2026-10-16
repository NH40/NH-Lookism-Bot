// Типы экрана «Биржа» (GET /api/exchange).
export interface ExItem {
  kind: "res" | "statist";
  code: string;
  amount: number;
  label: string;
  full: string;
}

export interface ExLot {
  id: number;
  seller: string;
  item: ExItem;
  price_res: string;
  price_label: string;
  price: number;
  price_full: string;
}

export interface ExAuction {
  id: number;
  seller: string;
  item: ExItem;
  price_res: string;
  price_label: string;
  min_bid: number;
  current_bid: number;
  next_bid: number;
  leading: boolean;
  mine: boolean;
  seconds_left: number;
  price_full: string;
}

export interface ExTrade {
  id: number;
  other: string;
  item: ExItem;
  price_res: string;
  price_label: string;
  price: number;
  price_full: string;
  seconds_left: number;
}

export interface ExResource {
  code: string;
  label: string;
  balance: number;
}

export interface ExSquad {
  code: string;
  label: string;
  total: number;
}

export interface ExConfig {
  lot_commission: number;
  auction_commission: number;
  auction_min_step: number;
  auction_hours: number[];
  max_lots: number;
  max_auctions: number;
  max_trades: number;
  trade_hours: number;
  resources: ExResource[];
  squads: ExSquad[];
}

export interface ExchangeData {
  lots: ExLot[];
  lots_has_more: boolean;
  auctions: ExAuction[];
  auctions_has_more: boolean;
  incoming: ExTrade[];
  outgoing: ExTrade[];
  my_lots: ExLot[];
  my_auctions: ExAuction[];
  config: ExConfig;
}
