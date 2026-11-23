import { useEffect, useRef } from "react";
import { getWebApp } from "../../telegram";

type Haptics = {
  impactOccurred?: (style: "light" | "medium" | "heavy") => void;
  notificationOccurred?: (kind: "success" | "error" | "warning") => void;
};
const haptics = () => (getWebApp() as unknown as { HapticFeedback?: Haptics } | null)?.HapticFeedback;

interface HudProps {
  label: string;
  /** Счёт и цель — тогда под строкой полоса прогресса (зеленеет на цели). Без них — только текст. */
  score?: number;
  need?: number;
  right?: string;
  /** Полоса «плохого» (пропущено из допустимого) — красная, рост = ошибка. */
  danger?: boolean;
  fmt?: (v: number) => string;
}

/** Общая шапка всех мини-игр (2026-11-23): счёт / цель, полоса, вибрация на попадание и ошибку. */
export function Hud({ label, score, need, right, danger, fmt = String }: HudProps) {
  const prev = useRef(score ?? 0);
  const lastTap = useRef(0);
  const pulse = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (score === undefined) return;
    const was = prev.current;
    prev.current = score;
    if (score === was) return;
    const h = haptics();
    const bad = danger ? score > was : score < was;
    if (bad) h?.notificationOccurred?.("error");
    else if (!danger && need !== undefined && was < need && score >= need) h?.notificationOccurred?.("success");
    else if (performance.now() - lastTap.current > 120) {
      lastTap.current = performance.now();
      h?.impactOccurred?.("light");
    }
    const el = pulse.current;
    if (el) {
      el.classList.remove("hit", "miss");
      void el.offsetWidth; // перезапуск анимации
      el.classList.add(bad ? "miss" : "hit");
    }
  }, [score]);
  const has = score !== undefined && need !== undefined && need > 0;
  const ratio = has ? Math.min(1, Math.max(0, score / need)) : 0;
  const reached = has && !danger && score >= need;
  return (
    <div className="mg-hud" ref={pulse}>
      <div className="mg-hud-row">
        <span>
          {label}
          {has && (
            <b className={reached ? "ok" : ""}>
              {" "}
              {fmt(Math.max(0, score))} / {fmt(need)}
              {reached ? " ✓" : ""}
            </b>
          )}
        </span>
        {right && <span className="mg-hud-right">{right}</span>}
      </div>
      {has && (
        <div className={`mg-hud-bar ${danger ? "danger" : reached ? "ok" : ""}`}>
          <div style={{ width: `${ratio * 100}%` }} />
        </div>
      )}
    </div>
  );
}
