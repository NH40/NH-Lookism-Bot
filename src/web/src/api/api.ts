import { getInitData } from "../telegram";

const API_BASE = "/api";

// Единственный реальный эндпоинт на данный момент — GET /api/profile (см.
// src/api/routers/profile.py, src/api/schemas.py: ProfileOut). Остальные 6 вкладок навигации
// не имеют рабочего backend'а ещё (см. CLAUDE.md) — им api-клиент не нужен, пока их роутеры
// остаются пустыми заглушками.

export interface Country {
  code: string;
  name: string;
}

export interface City {
  id: number;
  name: string;
  district_count: number;
}

export interface Profile {
  user_id: number;
  username: string | null;
  display_name: string | null;
  is_onboarded: boolean;
  country: Country | null;
  city: City | null;
  phase: string;
  gang_name: string | null;
}

// Ошибка API с сохранённым HTTP-статусом — вызывающему коду (useProfile) нужно отличать
// 404 ("игрок не жал /start боту") от прочих ошибок, не парся текст сообщения.
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "X-Telegram-Init-Data": getInitData() },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  return response.json() as Promise<T>;
}

export function fetchProfile(): Promise<Profile> {
  return apiFetch<Profile>("/profile");
}
