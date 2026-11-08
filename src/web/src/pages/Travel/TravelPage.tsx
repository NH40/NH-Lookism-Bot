import { Building2, Flag, MapPin } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { TravelCity, TravelData } from "../../types";
import { BackHeader, Panel, Screen, StatRow, countdown, fmt, useCountdown } from "../../components/ui";
import { ROUTE_MAP } from "../../constants/constants";
import { Sheet } from "../../components/Sheet";
import { useAction, useApi } from "../../hooks/useApi";
import "../Empire/Empire.css";

// Переезд (пользователь 2026-11-06): без районов — свободно по городам страны, смена страны — с КД;
// банда с районами сначала отказывается от них; круг при смене страны теряет районы и становится бандой.

function CityList({ country, exclude, onPick }: { country: string; exclude: number; onPick: (c: TravelCity) => void }) {
  const { data } = useApi<TravelCity[]>(`/travel/cities?country=${country}`);
  if (!data) return <p className="emp-note">Загружаю…</p>;
  return (
    <>
      {data
        .filter((c) => c.id !== exclude)
        .map((c) => (
          <button key={c.id} type="button" className="emp-row" style={{ width: "100%", color: "inherit", font: "inherit", textAlign: "left" }} onClick={() => onPick(c)}>
            <MapPin size={18} />
            <div className="grow"><b>{c.name}</b><small>{c.districts} районов</small></div>
          </button>
        ))}
    </>
  );
}

export function TravelPage() {
  const { data, status, error, reload } = useApi<TravelData>("/travel");
  const navigate = useNavigate();
  const [country, setCountry] = useState<string | null>(null);
  const [target, setTarget] = useState<TravelCity | null>(null);
  const [abandon, setAbandon] = useState(false);
  const { run, busy } = useAction(reload);
  const cd = useCountdown(data?.cooldown_seconds ?? 0);
  const cityCd = useCountdown(data?.city_cooldown_seconds ?? 0);

  const moveTo = async (city: TravelCity, acceptLosses: boolean) => {
    if (await run("/travel/move", { city_id: city.id, accept_losses: acceptLosses })) {
      setTarget(null);
      setCountry(null);
      navigate(ROUTE_MAP);
    }
  };
  const pickCity = (city: TravelCity) => {
    if (!data || cityCd > 0) return;
    if (country === null || country === data.country_code) void moveTo(city, false);
    else setTarget(city);
  };

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Переезд" subtitle={`${data.country} · ${data.city}`} backLabel="Карта" to={ROUTE_MAP} />
          <Panel title="СЕЙЧАС">
            <StatRow label="Город" value={`${data.city}, ${data.country}`} />
            <StatRow label="Твоих районов" value={data.districts ? `${fmt(data.districts)} в ${data.cities} гор.` : "0"} />
            {data.districts > 0 && <StatRow label="Зданий на них" value={fmt(data.buildings)} />}
            <p className="emp-note">
              {data.emperor
                ? "Император не покидает страну, пока на троне. Между её городами — свободно."
                : data.must_abandon
                  ? "Пока у тебя есть районы, переехать нельзя. Откажись от них: районы уйдут ботам, здания сгорят. Армия, уники и развитие останутся."
                  : data.circle
                    ? `Между городами страны — свободно, всё остаётся. Сменить страну можно раз в ${data.interval}, но районы и здания пропадут, и ты снова станешь бандой.`
                    : `Между городами страны — свободно. Сменить страну можно раз в ${data.interval}.`}
            </p>
            {cd > 0 && !data.emperor && <p className="emp-note">Сменить страну можно через {countdown(cd)}.</p>}
            <p className="emp-note">Между переездами — {data.city_interval}.{cityCd > 0 ? ` Следующий через ${countdown(cityCd)}.` : ""}</p>
            {data.under_challenge && <p className="emp-note">Против тебя висит вызов: отказаться от районов и сменить страну можно только после боя.</p>}
          </Panel>

          {data.must_abandon ? (
            <button className="btn red block" type="button" disabled={busy || data.under_challenge} onClick={() => setAbandon(true)}>
              <Flag size={16} />Отказаться от районов
            </button>
          ) : (
            <>
              <Panel title="КУДА">
                <div className="emp-rates" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
                  <button type="button" className={`pill ${country === null || country === data.country_code ? "on" : ""}`} style={{ minHeight: 40 }} onClick={() => setCountry(null)}>
                    {data.country}
                  </button>
                  {!data.emperor &&
                    data.countries.map((c) => (
                      <button key={c.code} type="button" className={`pill ${country === c.code ? "on" : ""}`} style={{ minHeight: 40 }} onClick={() => setCountry(c.code)}>
                        {c.name}
                      </button>
                    ))}
                </div>
              </Panel>
              <Panel title={country && country !== data.country_code ? "ГОРОДА · СМЕНА СТРАНЫ" : "ГОРОДА СТРАНЫ"}>
                <CityList key={country ?? data.country_code} country={country ?? data.country_code} exclude={data.city_id} onPick={pickCity} />
              </Panel>
            </>
          )}

          {target && (
            <Sheet title={`Переезд: ${target.name}`} onClose={() => setTarget(null)}>
              <p className="emp-note" style={{ margin: "0 0 10px" }}>Следующая смена страны — через {data.interval}.</p>
              {data.districts > 0 && (
                <p style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 700 }}>
                  Ты потеряешь {fmt(data.districts)} районов в {data.cities} гор. и {fmt(data.buildings)} зданий и станешь бандой. Отменить нельзя.
                </p>
              )}
              <button className="btn block" type="button" disabled={busy || cd > 0 || cityCd > 0 || data.under_challenge} onClick={() => moveTo(target, true)}>
                {cd > 0 ? `Через ${countdown(cd)}` : "Переехать"}
              </button>
            </Sheet>
          )}
          {abandon && (
            <Sheet title="Отказаться от районов?" onClose={() => setAbandon(false)}>
              <p style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 700 }}>
                <Building2 size={14} /> {fmt(data.districts)} районов уйдут ботам, {fmt(data.buildings)} зданий сгорят. Отменить нельзя.
              </p>
              <button className="btn red block" type="button" disabled={busy} onClick={async () => { if (await run("/travel/abandon")) setAbandon(false); }}>
                Да, отказаться
              </button>
            </Sheet>
          )}
        </div>
      )}
    </Screen>
  );
}
