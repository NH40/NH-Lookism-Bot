// Тонкая обёртка над window.Telegram.WebApp — единственный источник initData (авторизация,
// см. src/api/auth.py) и темы оформления. Портировано из Universe Anime Planet
// (src/web/src/telegram/telegram.ts) почти без изменений — тот же официальный алгоритм и
// тот же приём с CSS-переменными темы, см. CLAUDE.md UAP "Mini App: тема Telegram".

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: { id: number; first_name?: string; last_name?: string; username?: string; photo_url?: string } } & Record<string, unknown>;
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  ready: () => void;
  expand: () => void;
  close: () => void;
  BackButton: {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  HapticFeedback?: {
    impactOccurred?: (style: "light" | "medium" | "heavy") => void;
    notificationOccurred?: (type: "success" | "error" | "warning") => void;
  };
  openTelegramLink?: (url: string) => void;
  openInvoice?: (url: string, callback?: (status: "paid" | "cancelled" | "failed" | "pending") => void) => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp };
  }
}

export function getWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

export function getInitData(): string {
  return getWebApp()?.initData ?? "";
}

// Telegram НЕ проставляет CSS-переменные темы сам — читаем themeParams и выставляем их
// вручную, чтобы styles.css мог использовать var(--tg-theme-*, fallback). Безопасный
// no-op вне Telegram (обычный браузер при разработке).
export function applyTelegramTheme(): void {
  const webApp = getWebApp();
  if (!webApp) return;

  const root = document.documentElement;
  for (const [key, value] of Object.entries(webApp.themeParams)) {
    root.style.setProperty(`--tg-theme-${key.replace(/_/g, "-")}`, value);
  }
  root.dataset.colorScheme = webApp.colorScheme;
}
