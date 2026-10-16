// Карта страны (API `/api/country`) — круг и император.

export interface CountryCity {
  id: number;
  name: string;
  districts: number;
  bots: number;
  mine: number;
  owners: number;
  fully_mine: boolean;
}

export interface CountryData {
  available: boolean;
  country: string | null;
  emperor: boolean;
  influence: number;
  cities_mine: number;
  cities: CountryCity[];
}

export interface CityOwner {
  owner_id: number;
  label: string;
  districts: number;
  is_mine: boolean;
  challenged: boolean;
}

export interface CityData {
  id: number;
  name: string;
  districts: number;
  bots: number;
  bot_quantity: number;
  bot_rank: string | null;
  bot_power: number;
  owners: CityOwner[];
  attack_quantity: number;
  attack_power: number;
  emperor: boolean;
  cooldown_seconds: number;
}

export interface CityBattle {
  message: string;
  journal?: string[];
  won: boolean;
  captured: number;
  city: string;
  rounds: number;
  attacker_quantity: number;
  attacker_power: number;
  attacker_dead: number;
  attacker_fled: number;
  attacker_remaining_power: number;
  defender_power: number;
  defender_dead: number;
  influence: number;
  promoted: string | null;
  free_attack: boolean;
}
