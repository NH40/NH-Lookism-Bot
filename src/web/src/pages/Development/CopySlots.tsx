import { useAction, useApi } from "../../hooks/useApi";
import { Panel } from "../../components/ui";

// Слоты пути Копирования (2026-11-19): что копируется — видно, игрок сам занимает и освобождает слоты.
interface SlotsData { active: boolean; slots: number; taken: { slot: number; name: string; level: number }[]; memory: { id: number; name: string; level: number; copied: boolean }[] }

export function CopySlots() {
  const { data, reload } = useApi<SlotsData>("/development/path/copy-slots");
  const { run, busy } = useAction(reload);
  if (!data?.active) return null;
  const free = data.taken.length < data.slots;
  return (
    <Panel title={`Слоты копирования · ${data.taken.length}/${data.slots}`} tone="violet">
      <div className="muted dev-note">Копируется только то, что в слотах. Новый противник ложится сам только в свободный слот. Слотов: 1, +1 на 4, 7 и 10 уровне.</div>
      {data.taken.map((s) => (
        <div key={s.slot} className="row" style={{ marginTop: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 700 }}>{s.slot}. {s.name} · ур. {s.level}</span>
          <button type="button" className="btn ghost small" disabled={busy} onClick={() => run("/development/path/copy-slots", { slot: s.slot })}>Освободить</button>
        </div>
      ))}
      {free && data.memory.filter((m) => !m.copied).length > 0 && <div className="muted dev-note" style={{ marginTop: 10 }}>Память последних противников:</div>}
      {free && data.memory.filter((m) => !m.copied).map((m) => (
        <div key={m.id} className="row" style={{ marginTop: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{m.name} · ур. {m.level}</span>
          <button type="button" className="btn violet small" disabled={busy} onClick={() => run("/development/path/copy-slots", { memory_id: m.id })}>В слот</button>
        </div>
      ))}
    </Panel>
  );
}
