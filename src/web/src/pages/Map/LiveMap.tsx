import { Eye, Swords, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, imgUrl } from "../../api";
import { fmt } from "../../components/ui";
import { battlePath, ROUTE_INTEL } from "../../constants/constants";
import { useAction } from "../../hooks/useApi";

// Живая карта (2026-11-20): весь город полем плиток поверх арта, жетон банды «ходит» к выбранному району,
// снизу карточка района с действиями; обновление раз в 15 с.
export interface LiveDistrict { id: number; number: number; kind: "mine" | "bot" | "player"; owner: string | null; owner_id: number | null; bot_power: number | null }
interface LiveData { city: string; art: string | null; count: number; districts: LiveDistrict[] }

export function LiveMap({ onOpen }: { onOpen: (d: LiveDistrict) => void }) {
  const [data, setData] = useState<LiveData | null>(null);
  const [at, setAt] = useState<number | null>(null);
  const nav = useNavigate();
  const { run, busy } = useAction();
  useEffect(() => {
    const load = () => apiGet<LiveData>("/map/live").then(setData).catch(() => undefined);
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);
  const cols = useMemo(() => Math.max(3, Math.ceil(Math.sqrt(data?.districts.length ?? 9))), [data?.districts.length]);
  if (!data) return null;
  const home = data.districts.find((d) => d.kind === "mine");
  const pos = at ?? home?.id ?? data.districts[0]?.id;
  const idx = data.districts.findIndex((d) => d.id === pos);
  const sel = at !== null ? data.districts.find((d) => d.id === at) ?? null : null;
  const cell = 100 / cols;
  const rows = Math.ceil(data.districts.length / cols);
  return (
    <div className="lm">
      <div className="lm-field" style={{ aspectRatio: `${cols} / ${rows}`, backgroundImage: data.art ? `url(${imgUrl(data.art, 720)})` : undefined }}>
        {data.districts.map((d, i) => (
          <button key={d.id} type="button" className={`lm-tile ${d.kind} ${d.id === at ? "sel" : ""}`}
            style={{ left: `${(i % cols) * cell}%`, top: `${Math.floor(i / cols) * (100 / rows)}%`, width: `${cell}%`, height: `${100 / rows}%` }}
            onClick={() => setAt(d.id)}>
            <b>{d.number}</b>
            <small>{d.kind === "mine" ? "твой" : d.kind === "bot" ? "боты" : d.owner}</small>
          </button>
        ))}
        {idx >= 0 && (
          <div className="lm-token" style={{ left: `${(idx % cols) * cell + cell / 2}%`, top: `${(Math.floor(idx / cols) + 0.5) * (100 / rows)}%` }}>🥷</div>
        )}
      </div>
      {sel && (
        <div className="lm-card">
          <div className="lm-card-head">
            <b>Район №{sel.number}</b>
            <button type="button" className="btn ghost small" onClick={() => setAt(null)}><X size={14} /></button>
          </div>
          <small className="muted">
            {sel.kind === "mine" ? "Твой район" : sel.kind === "bot" ? `Боты · мощь ${fmt(sel.bot_power ?? 0)}` : `Владелец: ${sel.owner}`}
          </small>
          <div className="grid-3" style={{ gap: 6, marginTop: 8 }}>
            <button type="button" className="btn small" onClick={() => onOpen(sel)}>Подробнее</button>
            {sel.kind === "bot" && (
              <button type="button" className="btn gold small" disabled={busy} onClick={async () => {
                const r = (await run("/arena/start/district", { district_id: sel.id })) as { id?: string } | null;
                if (r?.id) nav(battlePath(r.id));
              }}><Swords size={14} /> Онлайн</button>
            )}
            {sel.kind === "player" && sel.owner_id && (
              <button type="button" className="btn violet small" onClick={() => nav(ROUTE_INTEL)}><Eye size={14} /> Разведать</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
