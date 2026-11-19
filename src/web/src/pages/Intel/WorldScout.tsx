import { Eye } from "lucide-react";
import { useState } from "react";
import { Panel, StatRow } from "../../components/ui";
import { useAction } from "../../hooks/useApi";

// Расширенная разведка (2026-11-20): клан, город, страна — глубина от уровня разведки и «разведывательных» путей/техник.
interface Report { title: string; level: number; lines: [string, string][]; top: [string, string][] }

export function ReportView({ r }: { r: Report }) {
  return (
    <div style={{ marginTop: 10 }}>
      <b style={{ fontSize: 14 }}>{r.title}</b>
      <div className="muted" style={{ fontSize: 11, fontWeight: 700, marginBottom: 6 }}>Глубина разведки: {r.level}/4</div>
      {r.lines.map(([k, v]) => <StatRow key={k} label={k} value={v} />)}
      {r.top.length > 0 && <div className="muted" style={{ fontSize: 11, fontWeight: 700, margin: "8px 0 4px" }}>Сильнейшие</div>}
      {r.top.map(([n, p], i) => <StatRow key={i} label={`${i + 1}. ${n}`} value={p} />)}
    </div>
  );
}

export function WorldScout({ country }: { country?: string }) {
  const [kind, setKind] = useState<"clan" | "country">("clan");
  const [name, setName] = useState("");
  const [rep, setRep] = useState<Report | null>(null);
  const { run, busy } = useAction();
  const go = async () => {
    const r = (await run("/intel/world", { kind, name: kind === "clan" ? name.trim() : (name.trim() || country) })) as unknown as Report | null;
    if (r?.title) setRep(r);
  };
  return (
    <Panel title="Разведка мира" tone="violet">
      <div className="grid-2" style={{ gap: 6 }}>
        <button type="button" className={`pill ${kind === "clan" ? "on" : ""}`} onClick={() => setKind("clan")}>Клан</button>
        <button type="button" className={`pill ${kind === "country" ? "on" : ""}`} onClick={() => setKind("country")}>Страна</button>
      </div>
      <input style={{ width: "100%", marginTop: 8, minHeight: 40, padding: "0 10px" }} value={name} onChange={(e) => setName(e.target.value)}
        placeholder={kind === "clan" ? "Название клана" : `Код страны (пусто — твоя${country ? `: ${country}` : ""})`} />
      <button type="button" className="btn violet block" style={{ marginTop: 8 }} disabled={busy || (kind === "clan" && !name.trim())} onClick={go}>
        <Eye size={16} /> Разведать
      </button>
      {rep && <ReportView r={rep} />}
    </Panel>
  );
}

export function CityScoutButton({ cityId }: { cityId: number }) {
  const [rep, setRep] = useState<Report | null>(null);
  const { run, busy } = useAction();
  return (
    <>
      <button type="button" className="btn violet block" style={{ marginTop: 8 }} disabled={busy}
        onClick={async () => { const r = (await run("/intel/world", { kind: "city", city_id: cityId })) as unknown as Report | null; if (r?.title) setRep(r); }}>
        <Eye size={16} /> Разведать город
      </button>
      {rep && <ReportView r={rep} />}
    </>
  );
}
