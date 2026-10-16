// UI-кит Mini App — компоненты утверждённого макета (холст «LBP 2.0 Mini App»). Экраны
// собираются ТОЛЬКО из них и классов styles.css — без своих цветов и рамок.
import { ChevronLeft, Loader2, ShieldAlert, AlertTriangle } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { LoadStatus } from "../hooks/useApi";

type Tone = "blue" | "gold" | "violet" | "green" | "red";

/** Панель с неоновой рамкой и бейджем-заголовком на рамке. */
export function Panel({ title, badgeMark = "i", tone = "blue", children, className = "" }: {
  title?: string;
  badgeMark?: string;
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${tone !== "blue" ? `tone-${tone}` : ""} ${title ? "" : "no-badge"} ${className}`}>
      {title && (
        <div className="panel-badge">
          <i>{badgeMark}</i>
          {title}
        </div>
      )}
      {children}
    </section>
  );
}

/** Полоса прогресса: `value` из `max`, цвет — `fill`. */
export function Bar({ value, max, fill = "blue" }: { value: number; max: number; fill?: "blue" | "red" | "violet" | "gold" | "green" }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div className="bar" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
      <div className={`fill-${fill}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

/** Плашка: иконка + значение + подпись. */
export function Chip({ icon, value, label, variant }: { icon?: ReactNode; value: ReactNode; label: string; variant?: "gold" | "violet" | "active" }) {
  return (
    <div className={`chip ${variant ?? ""}`}>
      {icon}
      <div className="chip-text">
        {value}
        <small>{label}</small>
      </div>
    </div>
  );
}

/** Строка стата с пунктиром снизу. */
export function StatRow({ icon, label, value }: { icon?: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="stat">
      {icon}
      {label}
      <b>{value}</b>
    </div>
  );
}

/** Шапка вложенного экрана: «‹ Назад» + заголовок. */
export function BackHeader({ title, subtitle, backLabel = "Назад", to }: { title: string; subtitle?: string; backLabel?: string; to?: string }) {
  const navigate = useNavigate();
  return (
    <div className="back-head">
      <button className="back-btn" type="button" onClick={() => (to ? navigate(to) : navigate(-1))}>
        <ChevronLeft size={18} strokeWidth={2.4} />
        {backLabel}
      </button>
      <div>
        <div className="back-title">{title}</div>
        {subtitle && <div className="muted" style={{ fontSize: 11, fontWeight: 700, textAlign: "right" }}>{subtitle}</div>}
      </div>
    </div>
  );
}

/** Состояния загрузки/ошибок экрана; `children` — когда данные готовы. */
export function Screen({ status, error, children }: { status: LoadStatus; error?: string | null; children: ReactNode }) {
  if (status === "loading") {
    return (
      <div className="page">
        <div className="skeleton" style={{ height: 110 }} />
        <div className="skeleton" style={{ height: 220 }} />
        <div className="skeleton" style={{ height: 160 }} />
      </div>
    );
  }
  if (status === "no-telegram") {
    return <div className="state"><ShieldAlert size={28} />Открой приложение через Telegram — из бота.</div>;
  }
  if (status === "not-registered") {
    return <div className="state"><AlertTriangle size={28} />Сначала нажми /start в боте и создай банду.</div>;
  }
  if (status === "error") {
    return <div className="state"><AlertTriangle size={28} />Не удалось загрузить.<span style={{ fontSize: 12 }}>{error}</span></div>;
  }
  return <>{children}</>;
}

export function Spinner({ size = 18 }: { size?: number }) {
  return <Loader2 size={size} className="spin" />;
}

// --- Тосты (результаты действий) ---

type ToastKind = "ok" | "err";
const ToastContext = createContext<(text: string, kind?: ToastKind) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; text: string; kind: ToastKind }[]>([]);
  const push = useCallback((text: string, kind: ToastKind = "ok") => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs.slice(-2), { id, text, kind }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 3500);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-wrap" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`} style={{ whiteSpace: "pre-line" }}>{t.text}</div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

/** Форматирование больших чисел: 1 240 000 → «1,24M», 12 480 → «12 480». */
export function fmt(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(abs >= 1e10 ? 1 : 2).replace(".", ",")}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(abs >= 1e7 ? 1 : 2).replace(".", ",")}M`;
  return n.toLocaleString("ru-RU");
}

/** Секунды → «1:04:12» / «04:12». */
export function countdown(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(sec).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** Секундный отсчёт от серверного значения (КД, таймеры событий). */
export function useCountdown(initial: number): number {
  const [left, setLeft] = useState(initial);
  useEffect(() => {
    setLeft(initial);
    if (initial <= 0) return;
    const id = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [initial]);
  return left;
}
