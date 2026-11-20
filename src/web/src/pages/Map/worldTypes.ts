// Живая карта страны (2026-11-20): типы ответов /map/world и /map/live, цвет клана.
export interface WorldCity {
  id: number; name: string; districts: number; bots: number; owners: number; mine: number; population: number;
  emperor: string | null; emperor_clan: number | null; top: string | null; top_share: number; clan: number | null;
}
export interface WorldBattle { id: string; city_id: number; district_id: number | null; kind: string; a: string; d: string; round: number }
export interface WorldFeed { ago: number; number: number; city_id: number; city: string; who: string; clan: number | null }
export interface WorldData {
  country: string; country_name: string; geo: string; my_city: number | null; my_clan: number | null;
  clans: Record<string, string>; cities: WorldCity[]; battles: WorldBattle[]; feed: WorldFeed[];
}
export interface Geo { w: number; h: number; path: string; cities: Record<string, [number, number]> }
export interface LiveDistrict {
  id: number; number: number; kind: "mine" | "bot" | "player"; owner: string | null; owner_id: number | null;
  clan: number | null; fresh: boolean; bot_power?: number | null;
}
export interface CityLive {
  city_id: number; city: string; count: number; emperor: string | null; own: boolean; art: string | null;
  clans: Record<string, string>; districts: LiveDistrict[];
}

/** Цвет клана: свой — бирюзовый, чужие — стабильный оттенок по id, без клана — серо-синий. */
export function clanColor(clan: number | null | undefined, myClan: number | null): string {
  if (!clan) return "#6b7fa8";
  if (clan === myClan) return "#4fd8ff";
  const hue = (clan * 137.508) % 360;
  return `hsl(${Math.round(hue)}, 78%, 58%)`;
}

export function agoText(s: number): string {
  if (s < 60) return "только что";
  if (s < 3600) return `${Math.floor(s / 60)} мин назад`;
  return `${Math.floor(s / 3600)} ч назад`;
}
