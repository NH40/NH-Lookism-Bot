// Переезд (API `/api/travel`).

export interface TravelData {
  phase: string;
  country_code: string;
  country: string;
  city_id: number;
  city: string;
  districts: number;
  buildings: number;
  cities: number;
  cooldown_seconds: number;
  interval: string;
  emperor: boolean;
  must_abandon: boolean;
  circle: boolean;
  countries: { code: string; name: string }[];
}

export interface TravelCity {
  id: number;
  name: string;
  districts: number;
}
