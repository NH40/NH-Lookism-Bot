import { HandCoins, Heart, Tag } from "lucide-react";
import { useEffect, useState } from "react";
import { apiGet } from "../../api";
import type { LoanRow } from "../../types";
import { StatRow, fmt } from "../../components/ui";
import { Sheet } from "../../components/Sheet";
import { useAction } from "../../hooks/useApi";

// Банки, 2026-11-19: прайс владельца (ресурсы в счёт долга), погашение ресурсом, прощение долга, профиль должника.
const digits = (v: string) => v.split("").filter((c) => c >= "0" && c <= "9").join("");
const num = (v: string) => Number(digits(v)) || 0;

interface Debtor {
  user_id: number; name: string; username: string | null; phase: string; league: string | null; power: number; nh_coins: number;
  districts: number; buildings: number; clan: string | null; loans_open: number; debt_total: number; frozen: boolean;
}

/** Прайс банка: NHCoin за единицу ресурса; пусто или 0 — ресурс не принимается. */
export function PricesSheet({ prices, resources, labels, onClose, reload }: {
  prices: Record<string, number>; resources: string[]; labels: Record<string, string>; onClose: () => void; reload: () => void;
}) {
  const { run, busy } = useAction(reload);
  const [draft, setDraft] = useState<Record<string, string>>(Object.fromEntries(resources.map((r) => [r, prices[r] ? String(prices[r]) : ""])));
  return (
    <Sheet title="Прайс банка" onClose={onClose}>
      <div className="bk-note">Сколько NHCoin долга гасит единица ресурса. Ресурс уходит тебе на счёт. Пусто — ресурс не принимаешь.</div>
      {resources.map((r) => (
        <label key={r} className="bk-field">
          <span className="muted">{labels[r] ?? r}</span>
          <input inputMode="numeric" value={draft[r] ?? ""} placeholder="не принимаю" onChange={(e) => setDraft({ ...draft, [r]: digits(e.target.value) })} />
        </label>
      ))}
      <button type="button" className="btn gold block" style={{ marginTop: 10 }} disabled={busy}
        onClick={async () => { if (await run("/bank/prices", { prices: Object.fromEntries(resources.map((r) => [r, num(draft[r] ?? "")])) })) onClose(); }}>
        <Tag size={15} /> Сохранить прайс
      </button>
    </Sheet>
  );
}

/** Заёмщик: погасить ресурсом по прайсу банка. */
export function ResourceRepay({ loan, labels, reload }: { loan: LoanRow; labels: Record<string, string>; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const entries = Object.entries(loan.prices ?? {});
  const [res, setRes] = useState(entries[0]?.[0] ?? "");
  const [units, setUnits] = useState("");
  if (!entries.length) return null;
  const price = loan.prices?.[res] ?? 0;
  const u = num(units);
  return (
    <div style={{ marginTop: 10 }}>
      <div className="bk-label">Погасить ресурсом (прайс банка)</div>
      <div className="bk-repay" style={{ gridTemplateColumns: "minmax(0, 1fr) 90px auto" }}>
        <select value={res} onChange={(e) => setRes(e.target.value)}>
          {entries.map(([r, p]) => <option key={r} value={r}>{labels[r] ?? r} · {fmt(p)} 🪙</option>)}
        </select>
        <input inputMode="numeric" value={units} placeholder="шт" onChange={(e) => setUnits(digits(e.target.value))} />
        <button type="button" className="btn ghost small" disabled={busy || u <= 0}
          onClick={async () => { if (await run("/bank/repay-resource", { loan_id: loan.id, resource: res, units: u })) setUnits(""); }}>
          <HandCoins size={14} />
        </button>
      </div>
      {u > 0 && <div className="bk-sub">гасит {fmt(Math.min(u * price, loan.debt))} 🪙 долга</div>}
    </div>
  );
}

/** Команда банка: профиль должника; владелец — простить долг целиком или часть. */
export function DebtorSheet({ loan, isOwner, onClose, reload }: { loan: LoanRow; isOwner: boolean; onClose: () => void; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const [card, setCard] = useState<Debtor | null>(null);
  const [failed, setFailed] = useState(false);
  const [part, setPart] = useState("");
  useEffect(() => {
    apiGet<Debtor>(`/bank/debtor/${loan.id}`).then(setCard).catch(() => setFailed(true));
  }, [loan.id]);
  const p = num(part);
  return (
    <Sheet title={`Должник · ${loan.name}`} onClose={onClose}>
      {failed && <div className="bk-empty">Профиль не загрузился.</div>}
      {!card && !failed && <div className="bk-empty">Загружаю…</div>}
      {card && (
        <>
          <StatRow label="Игрок" value={`${card.name}${card.username ? ` · @${card.username}` : ""}`} />
          <StatRow label="Мощь" value={fmt(card.power)} />
          <StatRow label="NHCoin" value={fmt(card.nh_coins)} />
          <StatRow label="Районы · здания" value={`${fmt(card.districts)} · ${fmt(card.buildings)}`} />
          {card.league && <StatRow label="Лига" value={card.league} />}
          <StatRow label="Клан" value={card.clan ?? "—"} />
          <StatRow label="Открытых кредитов" value={`${card.loans_open} · долг ${fmt(card.debt_total)}`} />
          {card.frozen && <div className="bk-timer red">Банда заморожена за долг</div>}
        </>
      )}
      <div className="bk-calc">
        <div><span>Долг по этому кредиту</span><b>{fmt(loan.debt)}</b></div>
      </div>
      {isOwner && (
        <>
          <div className="bk-repay" style={{ gridTemplateColumns: "minmax(0, 1fr) auto" }}>
            <input inputMode="numeric" value={part} placeholder="сколько простить" onChange={(e) => setPart(digits(e.target.value))} />
            <button type="button" className="btn ghost small" disabled={busy || p <= 0}
              onClick={async () => { if (await run("/bank/forgive", { loan_id: loan.id, amount: p })) onClose(); }}>Простить часть</button>
          </div>
          <button type="button" className="btn green block" style={{ marginTop: 8 }} disabled={busy}
            onClick={async () => { if (await run("/bank/forgive", { loan_id: loan.id })) onClose(); }}>
            <Heart size={15} /> Простить весь долг · {fmt(loan.debt)}
          </button>
          <div className="bk-note" style={{ marginTop: 6 }}>Прощённое в капитал не вернётся.</div>
        </>
      )}
    </Sheet>
  );
}
