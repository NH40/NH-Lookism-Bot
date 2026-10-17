// Общие кирпичи экранов админки: поля, выбор, подтверждение в два нажатия, пагинация.
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useApi } from "../../hooks/useApi";
import type { AdminMeta } from "../../types";

/** Справочники и права текущего админа (`GET /api/admin`). */
export function useAdminMeta() {
  return useApi<AdminMeta>("/admin");
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="adm-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function TextInput({ value, onChange, placeholder, type = "text" }: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: "text" | "number";
}) {
  return (
    <input
      className="adm-input"
      type="text"
      inputMode={type === "number" ? "numeric" : undefined}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.currentTarget.value)}
    />
  );
}

export function Select<T extends string | number>({ value, options, onChange }: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <select
      className="adm-select"
      value={String(value)}
      onChange={(e) => {
        const raw = e.currentTarget.value;
        const hit = options.find((o) => String(o.value) === raw);
        if (hit) onChange(hit.value);
      }}
    >
      {options.map((o) => (
        <option key={String(o.value)} value={String(o.value)}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

/** Вкладки-«пилюли» (класс .seg/.pill макета). */
export function Seg<T extends string>({ value, options, onChange, cols }: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  cols?: number;
}) {
  return (
    <div className="seg" style={{ gridTemplateColumns: `repeat(${cols ?? Math.min(options.length, 4)}, 1fr)`, marginBottom: 12 }}>
      {options.map((o) => (
        <button key={o.value} type="button" className={`pill ${o.value === value ? "on" : ""}`} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Опасное действие: первое нажатие — «Точно?», второе в течение 4 с — выполнить. */
export function ConfirmButton({ children, onConfirm, tone = "red", disabled, small }: {
  children: ReactNode;
  onConfirm: () => void;
  tone?: "red" | "gold" | "violet" | "ghost" | "green";
  disabled?: boolean;
  small?: boolean;
}) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<number | null>(null);
  useEffect(() => () => {
    if (timer.current) window.clearTimeout(timer.current);
  }, []);
  return (
    <button
      type="button"
      className={`btn ${armed ? "red" : tone} ${small ? "small" : "block"}`}
      disabled={disabled}
      onClick={() => {
        if (!armed) {
          setArmed(true);
          timer.current = window.setTimeout(() => setArmed(false), 4000);
          return;
        }
        if (timer.current) window.clearTimeout(timer.current);
        setArmed(false);
        onConfirm();
      }}
    >
      {armed ? "Точно? Нажми ещё раз" : children}
    </button>
  );
}

export function Pager({ page, total, perPage, onPage }: { page: number; total: number; perPage: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / perPage));
  return (
    <div className="adm-pager">
      <button type="button" className="btn ghost small" disabled={page <= 0} onClick={() => onPage(page - 1)}>
        <ChevronLeft size={14} />
      </button>
      <span>
        стр. {page + 1}/{pages} · всего {total}
      </span>
      <button type="button" className="btn ghost small" disabled={page + 1 >= pages} onClick={() => onPage(page + 1)}>
        <ChevronRight size={14} />
      </button>
    </div>
  );
}

/** Число со знаком из поля ввода: «1 000», «-500» → число; пусто/мусор → null. */
export function parseSigned(raw: string): number | null {
  const cleaned = raw.replace(/\s/g, "").replace(",", ".");
  if (!/^[-+]?\d+$/.test(cleaned)) return null;
  const n = Number(cleaned);
  return Number.isSafeInteger(n) ? n : null;
}

/** Поле числа + кнопки «Выдать» / «Забрать» (знак — по кнопке). */
export function GiveTakeForm({ busy, onSubmit, placeholder = "Количество" }: {
  busy: boolean;
  onSubmit: (delta: number) => Promise<unknown> | void;
  placeholder?: string;
}) {
  const [raw, setRaw] = useState("");
  const n = parseSigned(raw);
  const value = n === null ? null : Math.abs(n);
  const submit = async (sign: 1 | -1) => {
    if (!value) return;
    await onSubmit(sign * value);
    setRaw("");
  };
  return (
    <div className="adm-inline">
      <TextInput type="number" value={raw} onChange={setRaw} placeholder={placeholder} />
      <button type="button" className="btn green small" disabled={busy || !value} onClick={() => submit(1)}>
        Выдать
      </button>
      <button type="button" className="btn ghost small" disabled={busy || !value} onClick={() => submit(-1)}>
        Забрать
      </button>
    </div>
  );
}

/** Дата/время с сервера (ISO) → «16.10 21:05». */
export function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const pad = (x: number) => String(x).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${String(d.getFullYear()).slice(2)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function Kv({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <div className="adm-kv">
      {rows.map(([k, v]) => (
        <FragmentRow key={k} k={k} v={v} />
      ))}
    </div>
  );
}

function FragmentRow({ k, v }: { k: string; v: ReactNode }) {
  return (
    <>
      <span>{k}</span>
      <b>{v}</b>
    </>
  );
}
