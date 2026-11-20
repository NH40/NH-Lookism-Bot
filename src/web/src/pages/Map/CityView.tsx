import { ArrowLeft, Crown } from "lucide-react";
import { useEffect, useState } from "react";
import { apiGet } from "../../api";
import { fmt } from "../../components/ui";
import type { CityLive, LiveDistrict, WorldBattle } from "./worldTypes";
import { clanColor } from "./worldTypes";

const MINE_COLOR = "#2ee88a"; // свои районы — ярко-зелёные, не путать с бирюзой своего клана

// Город изнутри (2026-11-20): кварталы-районы на «ночной сетке улиц», жетоны банд, цвет клана,
// вспышка свежего захвата и пульс идущего боя. Обновление раз в 10 с.
export function CityView({ cityId, myClan, battles, onBack, onDistrict }: {
  cityId: number; myClan: number | null; battles: WorldBattle[]; onBack: () => void; onDistrict: (d: LiveDistrict, own: boolean) => void;
}) {
  const [data, setData] = useState<CityLive | null>(null);
  const [onlyMine, setOnlyMine] = useState(false);
  useEffect(() => {
    let alive = true;
    const load = () => apiGet<CityLive>(`/map/live?city_id=${cityId}`).then((d) => alive && setData(d)).catch(() => undefined);
    load();
    const t = setInterval(load, 10000);
    return () => { alive = false; clearInterval(t); };
  }, [cityId]);

  const fighting = new Set(battles.filter((b) => b.city_id === cityId && b.district_id).map((b) => b.district_id));
  const cols = data ? (data.count <= 4 ? 2 : data.count <= 8 ? 4 : data.count <= 16 ? 4 : 6) : 4;
  const owners = data ? new Map(data.districts.filter((d) => d.owner && d.kind !== "mine").map((d) => [d.owner as string, d.clan])) : new Map();

  return (
    <div className="cv">
      <div className="cv-head">
        <button type="button" className="btn ghost small" onClick={onBack}><ArrowLeft size={15} />Страна</button>
        <div style={{ minWidth: 0 }}>
          <b>{data?.city ?? "…"}</b>
          {data?.emperor && <small className="wm-emp"><Crown size={12} />{data.emperor}</small>}
        </div>
      </div>
      {!data ? <div className="skeleton" style={{ height: 260 }} /> : (
        <>
          {(() => {
            const mine = data.districts.filter((d) => d.kind === "mine");
            return (
              <div className="cv-mine">
                <div className="cv-mine-head">
                  <b>Твои районы: {mine.length}</b>
                  {mine.length > 0 && (
                    <button type="button" className={`pill ${onlyMine ? "on" : ""}`} onClick={() => setOnlyMine(!onlyMine)}>
                      {onlyMine ? "Показать все" : "Только мои"}
                    </button>
                  )}
                </div>
                {mine.length > 0 ? (
                  <div className="cv-mine-list">
                    {mine.map((d) => <button key={d.id} type="button" onClick={() => onDistrict(d, data.own)}>№{d.number}</button>)}
                  </div>
                ) : <small className="muted">{data.own ? "Пока ни одного — захвати район ботов ниже." : "В этом городе у тебя районов нет."}</small>}
              </div>
            );
          })()}
          <div className="cv-field" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
            {data.districts.map((d) => {
              const col = d.kind === "mine" ? MINE_COLOR : d.kind === "bot" ? null : clanColor(d.clan, myClan);
              if (onlyMine && d.kind !== "mine") return null;
              return (
                <button key={d.id} type="button" className={`cv-block ${d.kind} ${d.fresh ? "fresh" : ""} ${fighting.has(d.id) ? "fight" : ""}`}
                  style={col ? { ["--c" as string]: col } : undefined} onClick={() => onDistrict(d, data.own)}>
                  <span className="cv-num">{d.number}</span>
                  {d.kind === "mine" && <><span className="cv-mine-tag">ТВОЙ</span><span className="cv-token me">🥷</span></>}
                  {d.kind === "player" && <span className="cv-token" style={{ background: col ?? undefined }}>{(d.owner ?? "?").slice(0, 1).toUpperCase()}</span>}
                  {d.kind === "bot" && <span className="cv-bots">{d.bot_power ? fmt(d.bot_power) : "боты"}</span>}
                  {fighting.has(d.id) && <span className="cv-swords">⚔️</span>}
                  <small>{d.kind === "mine" ? "твой" : d.kind === "bot" ? "" : d.owner}</small>
                </button>
              );
            })}
          </div>
          {owners.size > 0 && (
            <div className="cv-legend">
              {[...owners.entries()].slice(0, 10).map(([name, clan]) => (
                <span key={name}><i style={{ background: clanColor(clan, myClan) }} />{name}{clan && data.clans[clan] ? ` · ${data.clans[clan]}` : ""}</span>
              ))}
            </div>
          )}
          <small className="muted" style={{ display: "block", marginTop: 2, fontWeight: 700 }}>
            {data.own ? "⚔️ Нажми на район ботов, чтобы атаковать, или на район игрока — бросить вызов." : "Чужой город — только просмотр. Воевать можно в своём городе."}
          </small>
        </>
      )}
    </div>
  );
}
