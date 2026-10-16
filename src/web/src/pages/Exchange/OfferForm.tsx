import { Gavel, Send, Tag } from "lucide-react";
import { useState } from "react";
import type { ExConfig } from "../../types";
import { Panel, fmt } from "../../components/ui";
import { useAction } from "../../hooks/useApi";

export type OfferMode = "lot" | "auction" | "trade";

const TITLES: Record<OfferMode, string> = { lot: "Выставить лот", auction: "Запустить аукцион", trade: "Предложить обмен" };

/** Общая форма выставления: предмет (ресурс или отряд статистов), цена в ресурсе, срок/адресат. */
export function OfferForm({ mode, cfg, onDone }: { mode: OfferMode; cfg: ExConfig; onDone: () => void | Promise<void> }) {
  const { run, busy } = useAction(onDone);
  const [item, setItem] = useState<string>("res:" + (cfg.resources[0]?.code ?? "coins"));
  const [amount, setAmount] = useState("1");
  const [priceRes, setPriceRes] = useState("coins");
  const [price, setPrice] = useState("");
  const [hours, setHours] = useState(cfg.auction_hours[cfg.auction_hours.length - 1] ?? 24);
  const [username, setUsername] = useState("");

  const [kind, code] = [item.slice(0, item.indexOf(":")), item.slice(item.indexOf(":") + 1)];
  const have = kind === "res" ? (cfg.resources.find((r) => r.code === code)?.balance ?? 0) : (cfg.squads.find((s) => s.code === code)?.total ?? 0);
  const amountN = Math.floor(Number(amount)) || 0;
  const priceN = Math.floor(Number(price)) || 0;
  const valid = amountN > 0 && amountN <= have && priceN > 0 && (mode !== "trade" || username.trim().length > 0);
  const commission = mode === "lot" ? cfg.lot_commission : mode === "auction" ? cfg.auction_commission : 0;
  const net = priceN - Math.floor(priceN * commission);

  const submit = async () => {
    const base = { item_kind: kind, item_code: code, amount: amountN, price_res: priceRes };
    const path = mode === "lot" ? "/exchange/lots/create" : mode === "auction" ? "/exchange/auctions/create" : "/exchange/trades/propose";
    const body = mode === "lot" ? { ...base, price: priceN } : mode === "auction" ? { ...base, min_bid: priceN, hours } : { ...base, price: priceN, username: username.trim() };
    const res = await run(path, body);
    if (res) {
      setAmount("1");
      setPrice("");
    }
  };

  return (
    <Panel title={TITLES[mode]} tone="gold" badgeMark={mode === "lot" ? "L" : mode === "auction" ? "A" : "T"}>
      <div className="muted ex-label">Что продаёшь</div>
      <div className="grid-3">
        {cfg.resources.map((r) => (
          <button key={r.code} type="button" className={`pill ${item === "res:" + r.code ? "on" : ""}`} onClick={() => setItem("res:" + r.code)}>
            {r.label}
            <span className="ex-sub">{fmt(r.balance)}</span>
          </button>
        ))}
        {cfg.squads.map((s) => (
          <button key={s.code} type="button" className={`pill ${item === "statist:" + s.code ? "on" : ""}`} onClick={() => setItem("statist:" + s.code)}>
            {s.label}
            <span className="ex-sub">{fmt(s.total)} бойц.</span>
          </button>
        ))}
      </div>

      <div className="grid-2 ex-fields">
        <label className="ex-field">
          <span className="muted">Количество (есть {fmt(have)})</span>
          <input inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))} />
        </label>
        <label className="ex-field">
          <span className="muted">{mode === "auction" ? "Стартовая ставка" : "Цена"}</span>
          <input inputMode="numeric" value={price} placeholder="0" onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))} />
        </label>
      </div>

      <label className="ex-field">
        <span className="muted">Цена в ресурсе</span>
        <select value={priceRes} onChange={(e) => setPriceRes(e.target.value)}>
          {cfg.resources.map((r) => (
            <option key={r.code} value={r.code}>
              {r.label}
            </option>
          ))}
        </select>
      </label>

      {mode === "auction" && (
        <div className="seg ex-hours" style={{ gridTemplateColumns: `repeat(${cfg.auction_hours.length}, minmax(0, 1fr))` }}>
          {cfg.auction_hours.map((h) => (
            <button key={h} type="button" className={`pill ${hours === h ? "on" : ""}`} onClick={() => setHours(h)}>
              {h} ч
            </button>
          ))}
        </div>
      )}
      {mode === "trade" && (
        <label className="ex-field">
          <span className="muted">Кому (@username)</span>
          <input value={username} placeholder="@username" onChange={(e) => setUsername(e.target.value)} />
        </label>
      )}

      <div className="grid-2 ex-fields">
        <div className="chip ex-chip">
          <span className="muted">Комиссия</span>
          <b>{mode === "trade" ? "нет" : `${Math.round(commission * 100)}%`}</b>
        </div>
        <div className="chip ex-chip">
          <span className="muted">Получишь</span>
          <b className="ex-gold">{priceN ? fmt(net) : "—"}</b>
        </div>
      </div>
      <div className="muted ex-hint">
        {mode === "lot" && `Не больше ${cfg.max_lots} лотов сразу. Предмет уходит в залог и вернётся при снятии.`}
        {mode === "auction" && `Не больше ${cfg.max_auctions} аукционов. Шаг ставки — от ${Math.round(cfg.auction_min_step * 100)}%; ставка в последнюю минуту продлевает торги.`}
        {mode === "trade" && `Не больше ${cfg.max_trades} предложений, живут ${cfg.trade_hours} ч. Предмет в залоге до ответа.`}
      </div>

      <button className="btn gold block" type="button" disabled={busy || !valid} onClick={() => void submit()}>
        {mode === "lot" ? <Tag size={18} /> : mode === "auction" ? <Gavel size={18} /> : <Send size={18} />}
        {mode === "lot" ? "Выставить" : mode === "auction" ? "Запустить" : "Отправить"}
      </button>
    </Panel>
  );
}
