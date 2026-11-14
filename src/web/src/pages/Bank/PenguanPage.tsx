import { Coins, Crown, Minus, Plus, ShoppingCart, Skull, Sparkles } from "lucide-react";
import { useState } from "react";
import type { PenguanBuilder, PenguanData } from "../../types";
import { BackHeader, Bar, Panel, Screen, StatRow, countdown, fmt, useCountdown } from "../../components/ui";
import { ROUTE_DEVELOPMENT } from "../../constants";
import { apiPost } from "../../api";
import { useAction, useApi, type LoadStatus } from "../../hooks/useApi";
import { useToast } from "../../components/ui";
import "./Bank.css";

/** Родословная Пеньгуана — «деньги — сила»: бафы от богатства, покупные бафы, выкупы, конструктор статистов. */
export function PenguanPage() {
  const { data, status, error, reload } = useApi<PenguanData>("/penguan");
  const { run, busy } = useAction(reload);
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Пеньгуан" subtitle="деньги — сила" backLabel="Развитие" to={`${ROUTE_DEVELOPMENT}?tab=blood`} />
          {!data.active ? (
            <Panel title="Родословная Пеньгуана" tone="gold">
              <div className="bk-note">Эти возможности открывает родословная Пеньгуана (первая или второго тела).</div>
            </Panel>
          ) : (
            <>
              <Panel title="Богатство" tone="gold">
                <div className="pg-wealth">
                  <span className="ico-box"><Crown size={20} /></span>
                  <div style={{ flex: 1 }}>
                    <small>очки богатства</small>
                    <div className="pg-points">{data.points.toFixed(2)}<small> / {data.points_cap}</small></div>
                  </div>
                </div>
                <Bar value={data.points} max={data.points_cap} fill="gold" />
                <StatRow label="Доход зданий в час" value={fmt(data.income)} />
                <StatRow label="Районы · города" value={`${data.districts} · ${data.cities}`} />
                {data.bonuses.length > 0 && <div className="pg-bonus">{data.bonuses.map((b) => <span key={b}>{b}</span>)}</div>}
              </Panel>
              {data.buffs.length > 0 && (
                <Panel title="Бафы на час" tone="violet">
                  {data.buffs.map((b) => <BuffRow key={b.kind} buff={b} busy={busy} onBuy={() => run("/penguan/buff", { kind: b.kind })} />)}
                </Panel>
              )}
              {(data.buyback || data.buyout) && (
                <Panel title="Выкупы">
                  {data.buyback && (
                    <div className="pg-buff">
                      <span className="ico-box"><Skull size={18} /></span>
                      <span className="pg-buff-main">
                        <b>Выкуп павших</b>
                        <small>{fmt(data.buyback.units)} бойцов последнего боя · мощь {fmt(data.buyback.power)}</small>
                      </span>
                      <button type="button" className="btn gold small" disabled={busy} onClick={() => run("/penguan/buyback")}>{fmt(data.buyback.price)}</button>
                    </div>
                  )}
                  {data.buyout && <BuyoutRow price={data.buyout.price} cooldown={data.buyout.cooldown} busy={busy} onBuy={() => run("/penguan/buyout")} />}
                </Panel>
              )}
              {data.builder && <Builder />}
            </>
          )}
        </div>
      )}
    </Screen>
  );
}

function BuffRow({ buff, busy, onBuy }: { buff: PenguanData["buffs"][number]; busy: boolean; onBuy: () => void }) {
  const left = useCountdown(buff.active_in);
  return (
    <div className="pg-buff">
      <span className="ico-box"><Sparkles size={18} /></span>
      <span className="pg-buff-main">
        <b>{buff.name}</b>
        <small>{buff.effect}{left > 0 && <span className="on"> · активен ещё {countdown(left)}</span>}</small>
      </span>
      <button type="button" className="btn gold small" disabled={busy || left > 0} onClick={onBuy}><Coins size={13} />{fmt(buff.price)}</button>
    </div>
  );
}

function BuyoutRow({ price, cooldown, busy, onBuy }: { price: number; cooldown: number; busy: boolean; onBuy: () => void }) {
  const left = useCountdown(cooldown);
  return (
    <div className="pg-buff">
      <span className="ico-box"><Crown size={18} /></span>
      <span className="pg-buff-main">
        <b>Выкуп района бота</b>
        <small>в своём городе, без боя{left > 0 ? ` · через ${countdown(left)}` : ""}</small>
      </span>
      <button type="button" className="btn gold small" disabled={busy || left > 0} onClick={onBuy}>{fmt(price)}</button>
    </div>
  );
}

const STEPS: { label: string; param: string; big?: number }[] = [
  { label: "Ранг", param: "rank" },
  { label: "Уровень", param: "level", big: 10 },
  { label: "Звёзды", param: "stars" },
  { label: "Школа", param: "school" },
  { label: "Ур. школы", param: "slevel" },
];

/** Конструктор статистов: настраиваешь бойца кнопками ±, покупаешь пачкой. */
function Builder() {
  const { data, status, reload } = useApi<PenguanBuilder>("/penguan/builder");
  const [view, setView] = useState<PenguanBuilder | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const { run } = useAction(async () => { setView(null); await reload(); });
  const v = view ?? data;
  const step = async (param: string, delta: number) => {
    if (busy) return;
    setBusy(true);
    try {
      setView(await apiPost<PenguanBuilder>("/penguan/builder/set", { param, delta }));
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "err");
    } finally {
      setBusy(false);
    }
  };
  if (!v) return <Panel title="Конструктор статистов"><div className="bk-empty">{(status as LoadStatus) === "error" ? "Конструктор недоступен." : "Загрузка…"}</div></Panel>;
  const value: Record<string, string> = {
    rank: `${v.rank} / ${v.ceiling}`, level: `${v.level} / ${v.level_cap}`, stars: `${v.stars} ★`, school: v.school_label, slevel: String(v.school_level),
  };
  return (
    <Panel title="Конструктор статистов" tone="green">
      {STEPS.map((s) => (
        <div key={s.param} className="pg-step">
          <span>{s.label}</span>
          <button type="button" className="btn ghost small" disabled={busy} onClick={() => void step(s.param, -(s.big ?? 1))}><Minus size={13} /></button>
          <b>{value[s.param]}</b>
          <button type="button" className="btn ghost small" disabled={busy} onClick={() => void step(s.param, s.big ?? 1)}><Plus size={13} /></button>
        </div>
      ))}
      <StatRow label="Мощь бойца" value={fmt(v.unit_power)} />
      <StatRow label="Цена бойца" value={fmt(v.unit_price)} />
      <StatRow label="Куплено сегодня (мощь)" value={`${fmt(v.bought_today)} / ${fmt(v.daily_cap)}`} />
      <Bar value={v.bought_today} max={v.daily_cap} fill="green" />
      {v.presets.length === 0 ? (
        <div className="bk-empty">Дневной лимит конструктора исчерпан.</div>
      ) : (
        <div className="pg-buys">
          {v.presets.map((n) => (
            <button key={n} type="button" className="btn green small" onClick={() => run("/penguan/builder/buy", { quantity: n })}>
              <ShoppingCart size={13} />{fmt(n)}
            </button>
          ))}
        </div>
      )}
    </Panel>
  );
}
