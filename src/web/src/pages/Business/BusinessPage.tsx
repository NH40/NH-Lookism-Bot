import { Clock, Coins, Landmark, MapPin, Package, TrendingUp } from "lucide-react";
import { useState } from "react";
import type { BusinessData } from "../../types";
import { BackHeader, Chip, Panel, Screen, StatRow, countdown, fmt } from "../../components/ui";
import { ROUTE_MORE } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import "./Business.css";

export function BusinessPage() {
  const { data, status, error, reload } = useApi<BusinessData>("/business");
  const { run, busy } = useAction(reload);
  const [sel, setSel] = useState<number | null>(null);
  const [confirmAll, setConfirmAll] = useState(false);
  const selDistrict = data?.district_list.find((d) => d.id === sel) ?? null;
  const anyFree = selDistrict ? selDistrict.free > 0 : (data?.district_list.some((d) => d.free > 0) ?? false);
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Бизнес" to={ROUTE_MORE} />
          <div className="grid-2">
            <Chip variant="gold" icon={<Coins size={18} color="#f5b942" />} value={fmt(data.nh_coins)} label="NHCoin" />
            <Chip icon={<TrendingUp size={18} color="#7fd4ff" />} value={`${fmt(data.per_minute)}/мин`} label="доход" />
          </div>
          <Panel title="Накоплено" tone="gold">
            <div className="row">
              <div>
                <div className="disp" style={{ fontSize: 24, fontWeight: 800, color: "var(--gold-2)" }}>
                  {fmt(data.pending)}
                </div>
                <div className="muted" style={{ fontSize: 12, fontWeight: 600, marginTop: 2 }}>
                  {data.pending <= 0
                    ? "доход копится каждую минуту"
                    : data.storage_full_in_seconds > 0
                      ? `хранилище заполнится через ${countdown(data.storage_full_in_seconds)}`
                      : "хранилище заполнено — доход сгорает"}
                </div>
              </div>
              <button className={`btn gold ${data.pending > 0 ? "" : "off"}`} disabled={busy || data.pending <= 0} onClick={() => run("/business/collect")}>
                Забрать
              </button>
            </div>
            {data.tax_percent ? (
              <div className="muted" style={{ fontSize: 11, fontWeight: 600, marginTop: 10 }}>
                Налог императору: {data.tax_percent}% уже вычтен из дохода.
              </div>
            ) : null}
          </Panel>
          <Panel title="Здания">
            {data.buildings.map((b) => (
              <StatRow key={b.code} icon={<Landmark size={16} color="#7fd4ff" />} label={b.name} value={`×${b.count}`} />
            ))}
            <StatRow icon={<Package size={16} color="#a78bfa" />} label="Вместимость района" value={`${data.capacity_per_district} мест`} />
            <StatRow icon={<Clock size={16} color="#3ddc84" />} label="Уровень бизнеса" value={data.level} />
            {data.gym_bonus_percent > 0 && <StatRow label="Бонус тренировки" value={`+${data.gym_bonus_percent}%`} />}
            {data.parliament_influence > 0 && <StatRow label="Влияние парламента" value={`+${data.parliament_influence}`} />}
          </Panel>
          <Panel title="Районы">
            {data.district_list.length === 0 && (
              <div className="muted" style={{ fontSize: 13, fontWeight: 700 }}>
                Районов пока нет — захвати первый на карте, и на нём можно будет строить.
              </div>
            )}
            {data.district_list.map((d) => (
              <button
                key={d.id}
                type="button"
                className={`biz-district ${sel === d.id ? "sel" : ""} ${d.free <= 0 ? "full" : ""}`}
                onClick={() => {
                  setConfirmAll(false);
                  setSel(sel === d.id ? null : d.id);
                }}
              >
                <div>
                  <b><MapPin size={13} style={{ verticalAlign: -2, marginRight: 4 }} />{d.city} №{d.number}</b>
                  <small>
                    {d.buildings.length ? d.buildings.map((b) => `${b.name} ×${b.count}`).join(" · ") : "пусто"} · мест {d.used}/{d.capacity}
                  </small>
                </div>
                <span className={`biz-tag ${d.free <= 0 ? "none" : ""}`}>
                  {sel === d.id ? "выбран" : d.free <= 0 ? "мест нет" : `свободно ${d.free}`}
                </span>
              </button>
            ))}
            {data.district_list.length > 0 && data.district_list.every((d) => d.free <= 0) && (
              <div className="muted biz-note">Все места заняты — улучши вместимость, чтобы строить ещё.</div>
            )}
          </Panel>
          {selDistrict && selDistrict.buildings.length > 0 && (
            <Panel title={`Снос — ${selDistrict.city} №${selDistrict.number}`} tone="red">
              {selDistrict.buildings.map((b) => (
                <div key={b.code} className="biz-item">
                  <div className="grow">
                    <b>{b.name}</b>
                    <small>на районе ×{b.count}</small>
                  </div>
                  <button className="btn red small" disabled={busy} onClick={() => run("/business/demolish", { district_id: selDistrict.id, type: b.code })}>
                    Снести 1
                  </button>
                </div>
              ))}
              <button
                className="btn red block"
                style={{ marginTop: 8 }}
                disabled={busy}
                onClick={async () => {
                  if (!confirmAll) return setConfirmAll(true);
                  setConfirmAll(false);
                  await run("/business/demolish", { district_id: selDistrict.id });
                }}
              >
                {confirmAll ? "Точно снести всё? Нажми ещё раз" : "Снести всё на районе"}
              </button>
              <div className="muted biz-note">NHCoin за снос не возвращаются — место освобождается под другую постройку.</div>
            </Panel>
          )}
          <Panel title="Постройка">
            {data.catalog.map((c) => {
              const afford = data.nh_coins >= c.cost;
              const ready = selDistrict !== null && selDistrict.free > 0 && afford;
              const readyAll = anyFree && afford;
              return (
                <div key={c.code} className="biz-item">
                  <div className="grow">
                    <b>{c.name}</b>
                    <small>{c.description}</small>
                  </div>
                  <div className="biz-cost">{c.cost === 0 ? "бесплатно" : fmt(c.cost)}</div>
                  <button
                    className={`btn small ${ready ? "" : "off"}`}
                    disabled={busy || !ready}
                    onClick={async () => {
                      if (sel !== null) await run("/business/build", { district_id: sel, type: c.code });
                    }}
                  >
                    Строить
                  </button>
                  <button
                    className={`btn gold small ${readyAll ? "" : "off"}`}
                    disabled={busy || !readyAll}
                    onClick={() => run("/business/build-all", { type: c.code, district_id: sel })}
                  >
                    Всё
                  </button>
                </div>
              );
            })}
            <div className="muted biz-note">
              {sel === null
                ? "«Всё» застроит свободные места во всех районах, пока хватит NHCoin. Чтобы строить по одному или снести — выбери район."
                : "«Строить» — одно здание на выбранном районе, «Всё» — все его свободные места."}
              {data.catalog.some((c) => c.free_first) && " Первое кафе — бесплатно."}
            </div>
          </Panel>
          <Panel title="Улучшения" tone="violet">
            {([
              { kind: "level", label: "Уровень дохода", cur: data.level, cost: data.level_cost },
              { kind: "capacity", label: "Мест на район", cur: data.capacity, cost: data.capacity_cost },
            ] as const).map((u) => {
              const maxed = u.cost === null;
              const afford = !maxed && data.nh_coins >= u.cost;
              return (
                <div key={u.kind} className="biz-item">
                  <div className="grow">
                    <b>{u.label}</b>
                    <small>{maxed ? `${u.cur} — максимум` : `${u.cur} → ${u.cur + 1}`} · предел {data.max_upgrade}</small>
                  </div>
                  {!maxed && <div className="biz-cost">{fmt(u.cost)}</div>}
                  <button
                    className={`btn violet small ${afford ? "" : "off"}`}
                    disabled={busy || !afford}
                    onClick={() => run("/business/upgrade", { kind: u.kind })}
                  >
                    {maxed ? "Макс" : "Улучшить"}
                  </button>
                </div>
              );
            })}
          </Panel>
        </div>
      )}
    </Screen>
  );
}
