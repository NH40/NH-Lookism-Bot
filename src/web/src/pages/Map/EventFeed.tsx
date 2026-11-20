import { Flag, Swords } from "lucide-react";
import { useState } from "react";
import type { WorldData } from "./worldTypes";
import { agoText, clanColor } from "./worldTypes";

// Лента страны (2026-11-20): сначала идущие бои, потом захваты районов за сутки.
export function EventFeed({ data, onCity }: { data: WorldData; onCity: (cityId: number) => void }) {
  const [all, setAll] = useState(false);
  const city = (id: number) => data.cities.find((c) => c.id === id)?.name ?? "";
  const items = [
    ...data.battles.map((b) => ({ key: b.id, live: true, cityId: b.city_id, text: `${b.a} ⚔ ${b.d}`, sub: `${city(b.city_id)} · раунд ${b.round + 1}`, clan: null as number | null })),
    ...data.feed.map((f, i) => ({ key: `f${i}`, live: false, cityId: f.city_id, text: `${f.who} захватил район №${f.number}`, sub: `${f.city} · ${agoText(f.ago)}`, clan: f.clan })),
  ];
  if (!items.length) return <p className="muted" style={{ fontSize: 12, fontWeight: 700, margin: 0 }}>В стране пока тихо. Захвати район — и попадёшь в ленту.</p>;
  return (
    <div className="ef">
      {(all ? items : items.slice(0, 6)).map((it) => (
        <button key={it.key} type="button" className={`ef-row ${it.live ? "live" : ""}`} onClick={() => onCity(it.cityId)}>
          <span className="ef-ico" style={!it.live ? { color: clanColor(it.clan, data.my_clan) } : undefined}>
            {it.live ? <Swords size={14} /> : <Flag size={14} />}
          </span>
          <span className="ef-txt"><b>{it.text}</b><small>{it.sub}</small></span>
          {it.live && <span className="ef-live">LIVE</span>}
        </button>
      ))}
      {items.length > 6 && (
        <button type="button" className="btn ghost small block" onClick={() => setAll(!all)}>{all ? "Свернуть" : `Ещё ${items.length - 6}`}</button>
      )}
    </div>
  );
}
