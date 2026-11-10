import { Gift, PartyPopper } from "lucide-react";
import { useState } from "react";
import { Panel, countdown, fmt } from "../../components/ui";
import { useAction, useApi } from "../../hooks/useApi";

type EventKind = {
  kind: string;
  title: string;
  about: string;
  active: { left_seconds: number; claims: number; pool: number; units: number | null } | null;
  cooldown_seconds: number;
};
type SubjectEvent = { id: number; kind: string; title: string; details: string; left_seconds: number; claimable: boolean };
type EventsData = {
  emperor: boolean;
  kinds: EventKind[];
  subjects: number;
  active_subjects: number;
  durations: number[];
  drill_prices: Record<string, number>;
  min_fund: number;
  max_days: number;
  events: SubjectEvent[];
};

const TIMED = ["feast", "holiday", "drill"];

function num(v: string): number {
  return Number(v.replace(/\s/g, "")) || 0;
}

function StartForm({ k, data, onDone }: { k: EventKind; data: EventsData; onDone: () => void }) {
  const { run, busy } = useAction(onDone);
  const [hours, setHours] = useState(data.durations[0] ?? 6);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [c, setC] = useState("");
  const [rank, setRank] = useState("");
  const input = (value: string, set: (v: string) => void, placeholder: string) => (
    <input className="emp-input" inputMode="numeric" placeholder={placeholder} value={value} onChange={(e) => set(e.currentTarget.value)} />
  );
  let fields = null;
  let body: Record<string, unknown> = { kind: k.kind, hours };
  if (k.kind === "coins") {
    fields = <div className="grid-2" style={{ gap: 6 }}>{input(a, setA, "NHCoin на игрока")}{input(b, setB, "Мест")}</div>;
    body = { kind: k.kind, amount: num(a), count: num(b) };
  } else if (k.kind === "statists") {
    fields = (
      <div className="grid-3" style={{ gap: 6 }}>
        <input className="emp-input" placeholder="Ранг, B+" value={rank} onChange={(e) => setRank(e.currentTarget.value)} />
        {input(a, setA, "Штук на игрока")}
        {input(b, setB, "Мест")}
      </div>
    );
    body = { kind: k.kind, rank, count: num(a), slots: num(b) };
  } else if (k.kind === "daily") {
    fields = <div className="grid-2" style={{ gap: 6 }}>{input(a, setA, "NHCoin в день")}{input(b, setB, `Дней (1–${data.max_days})`)}</div>;
    body = { kind: k.kind, amount: num(a), count: num(b) };
  } else if (k.kind === "tournament") {
    fields = input(a, setA, `Призовой фонд (от ${fmt(data.min_fund)})`);
    body = { kind: k.kind, amount: num(a) };
  } else if (k.kind === "feast") {
    fields = input(c, setC, `Фонд праздника (от ${fmt(data.min_fund)})`);
    body = { kind: k.kind, hours, amount: num(c) };
  }
  return (
    <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
      {TIMED.includes(k.kind) && (
        <div className="grid-3" style={{ gap: 6 }}>
          {data.durations.map((h) => (
            <button key={h} type="button" className={`btn small ${hours === h ? "" : "ghost"}`} onClick={() => setHours(h)}>{h} ч</button>
          ))}
        </div>
      )}
      {fields}
      {k.kind === "drill" && <p className="emp-note" style={{ margin: 0 }}>Цена: {fmt(data.drill_prices[String(hours)] ?? 0)} NHCoin (подданных за сутки: {fmt(data.active_subjects)})</p>}
      <button className="btn block gold" type="button" disabled={busy} onClick={() => run("/empire/events/start", body)}>
        <PartyPopper size={16} />Запустить
      </button>
    </div>
  );
}

export function EmperorEvents() {
  const { data, reload } = useApi<EventsData>("/empire/events");
  const [open, setOpen] = useState<string | null>(null);
  if (!data) return null;
  return (
    <Panel title="ИВЕНТЫ ИМПЕРИИ" tone="gold" badgeMark="★">
      <p className="emp-note" style={{ margin: "0 0 10px" }}>
        Подданных: {fmt(data.subjects)}, за сутки заходили {fmt(data.active_subjects)}. Всё оплачивается из твоих NHCoin, остаток фонда возвращается.
      </p>
      {data.kinds.map((k) => (
        <div key={k.kind} className="emp-ann">
          <button type="button" className="row" style={{ width: "100%", background: "none", border: 0, color: "inherit", padding: 0, textAlign: "left" }} onClick={() => setOpen(open === k.kind ? null : k.kind)}>
            <b>{k.title}</b>
            <small className="muted">
              {k.active ? `идёт · ${countdown(k.active.left_seconds)}` : k.cooldown_seconds ? `перезарядка ${countdown(k.cooldown_seconds)}` : "можно запустить"}
            </small>
          </button>
          {open === k.kind && (
            <>
              <p>{k.about}</p>
              {k.active ? (
                <small>Забрали: {k.active.claims} · фонд: {fmt(k.active.pool)}{k.active.units != null ? ` · статистов: ${fmt(k.active.units)}` : ""}</small>
              ) : (
                !k.cooldown_seconds && <StartForm k={k} data={data} onDone={reload} />
              )}
            </>
          )}
        </div>
      ))}
    </Panel>
  );
}

export function SubjectEvents() {
  const { data, reload } = useApi<EventsData>("/empire/events");
  const { run, busy } = useAction(reload);
  if (!data || data.events.length === 0) return null;
  return (
    <Panel title="ИВЕНТЫ ИМПЕРАТОРА" tone="gold" badgeMark="★">
      {data.events.map((e) => (
        <div key={e.id} className="emp-ann">
          <small>{e.title} · ещё {countdown(e.left_seconds)}</small>
          <p>{e.details}</p>
          {e.claimable && (
            <button className="btn small gold" type="button" disabled={busy} onClick={() => run(`/empire/events/${e.id}/claim`, {})}>
              <Gift size={14} />Забрать
            </button>
          )}
        </div>
      ))}
    </Panel>
  );
}
