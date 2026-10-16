import { Crosshair, Eye, Shield, Sparkles, Swords, Zap } from "lucide-react";
import type { ReactNode } from "react";
import type { StatsData } from "../../types";
import { BackHeader, Panel, Screen, fmt } from "../../components/ui";
import { ROUTE_PROFILE } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import "./Stats.css";

// Характеристики — прокачка рангов за очки развития (как экран «📊 Характеристики» бота).
const ICONS: Record<string, ReactNode> = {
  strength: <Swords size={18} color="#ff7a8a" />,
  speed: <Zap size={18} color="#7fd4ff" />,
  endurance: <Shield size={18} color="#3ddc84" />,
  agility: <Eye size={18} color="#f5c96a" />,
};
const MODE_LABELS: Record<string, string> = { "1": "+1", "5": "+5", max: "Макс" };

export function StatsPage() {
  const { data, status, error, reload } = useApi<StatsData>("/stats");
  const { run, busy } = useAction(reload);
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Характеристики" subtitle={`потенциал: ${data.potential}`} backLabel="Профиль" to={ROUTE_PROFILE} />
          <div className="grid-2">
            <div className="chip st-chip"><Sparkles size={18} color="#a78bfa" /><div><b>{fmt(data.dev_points)}</b><small>очков развития</small></div></div>
            <div className="chip st-chip"><Swords size={18} color="#ff7a8a" /><div><b>+{data.strength_power_percent}%</b><small>к мощи от силы</small></div></div>
          </div>
          <Panel title="РАНГИ">
            {data.stats.map((s) => (
              <div key={s.code} className="st-row">
                <div className="st-head">
                  {ICONS[s.code] ?? <Crosshair size={18} />}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="st-name">{s.label} <span>{s.rank}</span></div>
                    <div className="st-effect">{s.effect}</div>
                  </div>
                  <div className="st-cost">{s.next_cost === null ? "максимум" : `след. — ${fmt(s.next_cost)} оч.`}</div>
                </div>
                {s.next_cost !== null && (
                  <div className="grid-3" style={{ marginTop: 8 }}>
                    {data.modes.map((m) => (
                      <button key={m} className="btn small" type="button" disabled={busy || data.dev_points < (s.next_cost ?? 0)} onClick={() => run("/stats/up", { stat: s.code, mode: m })}>
                        {MODE_LABELS[m] ?? m}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </Panel>
          <p className="muted" style={{ margin: 0, fontSize: 11, fontWeight: 700, lineHeight: 1.45 }}>
            Очки даёт личная тренировка (раз в час), их число зависит от потенциала. Каждый следующий ранг стоит дороже.
          </p>
        </div>
      )}
    </Screen>
  );
}
