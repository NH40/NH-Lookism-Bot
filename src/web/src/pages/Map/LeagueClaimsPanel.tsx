import { Swords } from "lucide-react";
import { Panel, countdown } from "../../components/ui";
import { useAction, useApi } from "../../hooks/useApi";

// Заявки на районы после перехода в лигу (2026-11-23): район в новой лиге занят — 24 часа на бесплатный вызов.
interface Claim { id: number; number: number; city: string; expires_at: string; in_progress: boolean }

export function LeagueClaimsPanel() {
  const { data, reload } = useApi<{ claims: Claim[] }>("/league/claims");
  const { run, busy } = useAction(reload);
  if (!data || data.claims.length === 0) return null;
  return (
    <Panel title="Отбить районы после перехода">
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        Эти районы в новой лиге заняты. Здания отложены: победишь — район и здания твои, нет или не успеешь — вернутся NHCoin.
      </div>
      {data.claims.map((c) => {
        const left = Math.max(0, Math.round((new Date(c.expires_at).getTime() - Date.now()) / 1000));
        return (
          <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0" }}>
            <div style={{ flex: 1 }}>
              <b>Район №{c.number}</b> · {c.city}
              <div className="muted" style={{ fontSize: 11 }}>{c.in_progress ? "вызов идёт" : `осталось ${countdown(left)}`}</div>
            </div>
            <button type="button" className="btn small gold" disabled={busy || c.in_progress} onClick={() => run(`/league/claims/${c.id}`)}>
              <Swords size={14} /> Вызов
            </button>
          </div>
        );
      })}
    </Panel>
  );
}
