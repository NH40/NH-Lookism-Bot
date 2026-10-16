import { getInitData } from "../telegram";

const API_BASE = "/api";

// Ошибка API с HTTP-статусом и текстом `detail` от FastAPI — экраны отличают 404 («игрок
// не жал /start») от остальных и показывают `detail` игроку в тосте.
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "X-Telegram-Init-Data": getInitData(),
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch {
      /* тело не JSON — оставляем statusText */
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>("GET", path);
}

export function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  return request<T>("POST", path, body);
}

/** URL картинки из `assets/` (уменьшенное WebP-превью нужной ширины, см. api/routers/img.py). */
export function imgUrl(path: string | null | undefined, width = 480): string | undefined {
  if (!path) return undefined;
  return `${API_BASE}/img/${path.split("/").map(encodeURIComponent).join("/")}?w=${width}`;
}

/** Ответ любого действия (POST): текст для тоста. Экраны после него перезагружают данные. */
export interface ActionResult {
  message: string;
}
