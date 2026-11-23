import { Siren } from "lucide-react";
import { OnlineBattleButton } from "../../components/OnlineBattleButton";
import { Panel, countdown, fmt, useCountdown } from "../../components/ui";
import { useAction, useApi } from "../../hooks/useApi";

// Рейд на земли (2026-11-19): за час предупреждение; бьёт по самому сильному лагерю — и заранее, и по сроку (2026-11-24).
interface RaidData { pending: { difficulty: string; power: number; starts_in: number; lose: number } | null }

export function RaidBanner() {
  const { data, reload } = useApi<RaidData>("/raid");
  const { run, busy } = useAction(reload);
  const left = useCountdown(data?.pending?.starts_in ?? 0);
  const p = data?.pending;
  if (!p) return null;
  return (
    <Panel title="Рейд на твои земли" tone="red">
      <div style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.45 }}>
        <Siren size={14} /> Сложность <b>{p.difficulty}</b> · сила ≈ <b>{fmt(p.power)}</b> · придёт через <b>{countdown(left)}</b>.<br />
        Рейд бьёт по твоему самому сильному лагерю — и сейчас, и когда придёт. Поражение — районов ботам: {p.lose}.
      </div>
      <button type="button" className="btn red block" style={{ marginTop: 10 }} disabled={busy} onClick={() => run("/raid/fight")}>Встретить рейд</button>
      <OnlineBattleButton path="/arena/start/raid" label="Встретить онлайн: перки и ходы" disabled={busy} />
    </Panel>
  );
}
