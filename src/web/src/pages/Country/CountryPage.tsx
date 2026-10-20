import { ChevronRight, Flag, Home, Shield, Skull, Swords, Users } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { CityBattle, CityData, CityOwner, CountryData } from "../../types";
import { BackHeader, Panel, Screen, StatRow, countdown, fmt, useCountdown } from "../../components/ui";
import { Sheet } from "../../components/Sheet";
import { Journal } from "../../components/Journal";
import { ROUTE_MAP } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import "./Country.css";

// Карта страны (круг и император) — как карта страны в боте: круг берёт город целиком —
// ботов одним боем, игрока вызовом за все его районы в городе. Императору захват своей
// страны недоступен — только просмотр.

function BattleResult({ r, onClose }: { r: CityBattle; onClose: () => void }) {
  return (
    <>
      <div className={`res-head ${r.captured ? "win" : "lose"}`}>
        {r.captured ? <Flag size={20} /> : <Skull size={20} />}
        {r.message}
      </div>
      <StatRow label="Раундов" value={r.rounds} />
      <StatRow label="Твоя армия" value={`${fmt(r.attacker_quantity)} · мощь ${fmt(r.attacker_power)}`} />
      <StatRow label="Потери" value={fmt(r.attacker_dead)} />
      <StatRow label="Сбежали" value={fmt(r.attacker_fled)} />
      <StatRow label="Осталось мощи" value={fmt(r.attacker_remaining_power)} />
      <StatRow label="Мощь ботов" value={fmt(r.defender_power)} />
      <StatRow label="Потери ботов" value={fmt(r.defender_dead)} />
      <StatRow label="Влияние" value={`+${fmt(r.influence)}`} />
      {r.promoted && <p className="ct-note">{r.promoted}</p>}
      {r.free_attack && <p className="ct-note">Ловкость: вторая атака — перерыв на сражения не поставлен.</p>}
      <Journal lines={r.journal} />
      <button className="btn block" type="button" style={{ marginTop: 12 }} onClick={onClose}>Закрыть</button>
    </>
  );
}

function CityView({ cityId }: { cityId: number }) {
  const { data, status, error, reload } = useApi<CityData>(`/country/city/${cityId}`);
  const { run, busy } = useAction(reload);
  const [result, setResult] = useState<CityBattle | null>(null);
  const [target, setTarget] = useState<CityOwner | null>(null);
  const cd = useCountdown(data?.cooldown_seconds ?? 0);

  const attack = async () => {
    const r = await run(`/country/city/${cityId}/attack-bots`);
    if (r) setResult(r as unknown as CityBattle);
  };
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title={data.name} subtitle={`${data.districts} районов`} backLabel="Страна" />
          <Panel title="БОТЫ ГОРОДА" badgeMark="⚔">
            {data.bots ? (
              <>
                <StatRow icon={<Shield size={16} color="#ff8aa0" />} label="Районов у ботов" value={data.bots} />
                <StatRow icon={<Users size={16} color="#7fd4ff" />} label="Отряд" value={`${fmt(data.bot_quantity)} · ${data.bot_rank ?? "—"}`} />
                <StatRow icon={<Swords size={16} color="#ff8aa0" />} label="Мощь ботов" value={fmt(data.bot_power)} />
                {!data.emperor && (
                  <button className="btn block" type="button" style={{ marginTop: 12 }} disabled={busy || cd > 0} onClick={attack}>
                    <Swords size={16} />
                    {cd > 0 ? `Перерыв ${countdown(cd)}` : `Штурм ботов · ${data.bots} р-нов`}
                  </button>
                )}
              </>
            ) : (
              <p className="ct-note" style={{ margin: 0 }}>Ботов в городе не осталось.</p>
            )}
          </Panel>
          <Panel title="ИГРОКИ В ГОРОДЕ">
            {data.owners.length === 0 ? (
              <p className="ct-note" style={{ margin: 0 }}>Районов у игроков нет.</p>
            ) : (
              data.owners.map((o) => (
                <div key={o.owner_id} className="ct-row">
                  <Users size={18} color={o.is_mine ? "var(--green-2, #8ff0b8)" : "var(--violet-2)"} />
                  <div className="grow">
                    <b>{o.label}{o.is_mine ? " · ты" : ""}</b>
                    <small>{o.districts} р-нов{o.challenged ? " · вызов уже брошен" : ""}</small>
                  </div>
                  {!data.emperor && !o.is_mine && !o.challenged && (
                    <button className="btn small violet" type="button" disabled={busy || cd > 0} onClick={() => setTarget(o)}>Вызов</button>
                  )}
                </div>
              ))
            )}
            <p className="ct-note">Вызов — за все районы игрока в этом городе; у него время на принятие, не принял — бой против его лагеря защиты.</p>
          </Panel>
          <Panel title="ТВОЯ АРМИЯ" tone="green">
            <StatRow icon={<Swords size={16} color="#7fd4ff" />} label={`Лагерь атаки: ${fmt(data.attack_quantity)}`} value={fmt(data.attack_power)} />
          </Panel>
          {data.emperor && <p className="ct-note">Император не захватывает свою страну — его поле боя: войны императоров.</p>}
        </div>
      )}
      {result && (
        <Sheet title={result.city} onClose={() => setResult(null)}>
          <BattleResult r={result} onClose={() => setResult(null)} />
        </Sheet>
      )}
      {target && (
        <Sheet title={`Вызов: ${target.label}`} onClose={() => setTarget(null)}>
          <p className="ct-note" style={{ marginTop: 0 }}>Бой за все его районы в городе ({target.districts}). Итог придёт в чат с ботом.</p>
          <button className="btn violet block" type="button" disabled={busy} onClick={async () => { if (await run(`/country/city/${cityId}/challenge`, { owner_id: target.owner_id })) setTarget(null); }}>
            <Swords size={16} />Бросить вызов
          </button>
        </Sheet>
      )}
    </Screen>
  );
}

export function CountryPage() {
  const [params, setParams] = useSearchParams();
  const cityId = Number(params.get("city")) || null;
  const { data, status, error, reload } = useApi<CountryData>(cityId ? null : "/country");
  const { run, busy } = useAction(reload);
  if (cityId) return <CityView cityId={cityId} />;
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title={data.country ?? "Страна"} subtitle={`${data.cities.length} гор. · целиком твоих ${data.cities_mine}`} backLabel="Карта" to={ROUTE_MAP} />
          {!data.available ? (
            <Panel title="СТРАНА"><p className="ct-note" style={{ margin: 0 }}>Карта страны открывается на фазе круга — пока воюй за районы своего города.</p></Panel>
          ) : (
            <>
              <div className="grid-2">
                <div className="chip ct-chip"><span className="muted">Городов</span><span className="disp">{data.cities.length}</span></div>
                <div className="chip ct-chip"><span className="muted">Влияние</span><span className="disp">{fmt(data.influence)}</span></div>
              </div>
              {data.throne?.can_challenge && (
                <Panel title="ТРОН" tone="gold" badgeMark="👑">
                  <p className="ct-note" style={{ marginTop: 0 }}>
                    Вся страна твоя, но её города держит император. Сначала бои с чужими императорами по очереди, потом — за трон.
                  </p>
                  <button className="btn gold block" type="button" disabled={busy} onClick={() => run("/country/throne")}>
                    Бой за трон
                  </button>
                </Panel>
              )}
              {data.throne && !data.throne.can_challenge && data.throne.has_emperor && data.throne.missing > 0 && (
                <Panel title="ТРОН" badgeMark="👑">
                  <p className="ct-note" style={{ margin: 0 }}>
                    Чтобы вызвать императора на бой за трон, захвати все районы страны — осталось {fmt(data.throne.missing)}.
                  </p>
                </Panel>
              )}
              <Panel title="ГОРОДА">
                <p className="ct-note" style={{ marginTop: 0 }}>
                  {data.emperor ? "Свою страну император не захватывает — только смотрит." : "Круг берёт город целиком: ботов — одним боем, игрока — вызовом за все его районы."}
                </p>
                {data.cities.map((c) => (
                  <button key={c.id} type="button" className="ct-row ct-btn" onClick={() => setParams({ city: String(c.id) })}>
                    <Home size={18} color={c.fully_mine ? "var(--green-2, #8ff0b8)" : "var(--cyan-2)"} />
                    <span className="grow">
                      <b>{c.name}{c.fully_mine ? " · твой" : ""}</b>
                      <small>{c.districts} р-нов · боты {c.bots} · твоих {c.mine} · игроков {c.owners}</small>
                    </span>
                    <ChevronRight size={16} />
                  </button>
                ))}
              </Panel>
            </>
          )}
        </div>
      )}
    </Screen>
  );
}
