import { Banknote, ChevronLeft, ChevronRight, Landmark, Lock, PiggyBank, Plus, Settings2, Snowflake, Trash2, Wallet } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { BankHome, BankRow, LoanRow } from "../../types";
import { BackHeader, Bar, Chip, Panel, Screen, StatRow, countdown, fmt, useCountdown } from "../../components/ui";
import { Sheet } from "../../components/Sheet";
import { ROUTE_MORE } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import "./Bank.css";

type Tab = "banks" | "loans" | "mine";

const num = (v: string) => Math.floor(Number(v.replace(/\D/g, ""))) || 0;

/** Банки игроков и кредиты — как «💳 Кредиты» в боте: список банков, мои кредиты, мой банк. */
export function BankPage() {
  const [page, setPage] = useState(0);
  const { data, status, error, reload } = useApi<BankHome>(`/bank?page=${page}`);
  const [params] = useSearchParams();
  const initial = params.get("tab");
  const [tab, setTab] = useState<Tab>(initial === "loans" || initial === "mine" ? initial : "banks");
  const shownTab: Tab = data?.frozen ? "loans" : tab;
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Кредиты" subtitle="банки игроков" to={ROUTE_MORE} />
          {data.frozen && (
            <Panel title="Банда заморожена" tone="red">
              <div className="bk-note">
                Долг не вернули к сроку. Всё заблокировано, весь доход уходит в долг. Погаси кредит — иначе банда удалится.
              </div>
            </Panel>
          )}
          <div className="grid-2">
            <Chip icon={<Wallet size={18} />} value={fmt(data.coins)} label="NHCoin на счёте" variant="gold" />
            <Chip icon={<Banknote size={18} />} value={fmt(data.loans.reduce((s, l) => s + l.debt, 0))} label="твой долг" variant={data.loans.length ? "violet" : undefined} />
          </div>
          {!data.frozen && (
            <div className="seg" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
              <button type="button" className={`pill ${shownTab === "banks" ? "on" : ""}`} onClick={() => setTab("banks")}>Банки</button>
              <button type="button" className={`pill ${shownTab === "loans" ? "on" : ""}`} onClick={() => setTab("loans")}>
                Мои кредиты{data.loans.length ? ` · ${data.loans.length}` : ""}
              </button>
              <button type="button" className={`pill ${shownTab === "mine" ? "on" : ""}`} onClick={() => setTab("mine")}>Мой банк</button>
            </div>
          )}
          {shownTab === "banks" && <BanksTab data={data} page={page} setPage={setPage} reload={reload} />}
          {shownTab === "loans" && <LoansTab data={data} reload={reload} />}
          {shownTab === "mine" && <MineTab data={data} reload={reload} />}
        </div>
      )}
    </Screen>
  );
}

function BanksTab({ data, page, setPage, reload }: { data: BankHome; page: number; setPage: (p: number) => void; reload: () => void }) {
  const [pick, setPick] = useState<BankRow | null>(null);
  return (
    <>
      <Panel title="Банки игроков">
        <div className="bk-note" style={{ marginBottom: 10 }}>
          Ставка — процент в день от остатка долга, сначала самые дешёвые. Не вернул к сроку: долг заберут монетами → статистами → зданиями,
          не хватило — заморозка на {data.limits.freeze_days} дн., потом удаление банды.
        </div>
        {data.banks.length === 0 && <div className="bk-empty">Банков пока нет — создай свой во вкладке «Мой банк».</div>}
        {data.banks.map((b) => (
          <button key={b.id} type="button" className="bk-bank" onClick={() => setPick(b)}>
            <span className="ico-box"><Landmark size={18} /></span>
            <span className="bk-bank-main">
              <b>{b.owner}</b>
              <small>{b.min_days}–{b.max_days} дн. · кредитов {b.open_loans}</small>
            </span>
            <span className="bk-bank-side">
              <b className="bk-rate">{b.rate_label}<em>/день</em></b>
              <small>до {fmt(b.capital)}</small>
            </span>
          </button>
        ))}
        {(page > 0 || data.more) && (
          <div className="row" style={{ marginTop: 10 }}>
            <button type="button" className="btn ghost small" disabled={page === 0} onClick={() => setPage(page - 1)}><ChevronLeft size={14} />Назад</button>
            <span className="muted mono" style={{ fontSize: 12 }}>стр. {page + 1}</span>
            <button type="button" className="btn ghost small" disabled={!data.more} onClick={() => setPage(page + 1)}>Вперёд<ChevronRight size={14} /></button>
          </div>
        )}
      </Panel>
      {pick && <TakeSheet bank={pick} minLoan={data.limits.min_loan} onClose={() => setPick(null)} reload={reload} />}
    </>
  );
}

function TakeSheet({ bank, minLoan, onClose, reload }: { bank: BankRow; minLoan: number; onClose: () => void; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const [amount, setAmount] = useState("");
  const [days, setDays] = useState(bank.min_days);
  const a = num(amount);
  const perDay = Math.max(1, Math.round(a * bank.rate));
  const valid = a >= minLoan && a <= bank.capital;
  const dayList = Array.from({ length: bank.max_days - bank.min_days + 1 }, (_, i) => bank.min_days + i);
  const submit = async () => {
    if (await run("/bank/take", { bank_id: bank.id, amount: a, days })) onClose();
  };
  return (
    <Sheet title={`Банк ${bank.owner}`} onClose={onClose}>
      <StatRow label="Ставка" value={`${bank.rate_label} в день`} />
      <StatRow label="Можно взять" value={`${fmt(minLoan)} – ${fmt(bank.capital)}`} />
      <label className="bk-field">
        <span className="muted">Сумма кредита</span>
        <input inputMode="numeric" value={amount} placeholder={String(minLoan)} onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))} />
      </label>
      <div className="bk-quick">
        {[0.25, 0.5, 1].map((k) => (
          <button key={k} type="button" className="pill" onClick={() => setAmount(String(Math.max(minLoan, Math.floor(bank.capital * k))))}>
            {k === 1 ? "максимум" : `${k * 100}%`}
          </button>
        ))}
      </div>
      <div className="muted bk-label">Срок, дней</div>
      <div className="bk-days">
        {dayList.map((d) => (
          <button key={d} type="button" className={`pill ${days === d ? "on" : ""}`} onClick={() => setDays(d)}>{d}</button>
        ))}
      </div>
      {valid && (
        <div className="bk-calc">
          <div><span>Проценты в сутки</span><b>~{fmt(perDay)}</b></div>
          <div><span>Вернуть в последний день</span><b className="bk-gold">{fmt(a + perDay * days)}</b></div>
          <small>Первые сутки процентов — сразу. Гаси раньше — заплатишь меньше.</small>
        </div>
      )}
      <button type="button" className="btn gold block" disabled={busy || !valid} onClick={() => void submit()}>
        <Banknote size={16} /> Взять {a ? fmt(a) : ""}
      </button>
    </Sheet>
  );
}

function LoanCard({ loan, reload }: { loan: LoanRow; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const [part, setPart] = useState("");
  const due = useCountdown(loan.due_in);
  const frozenLeft = useCountdown(loan.frozen_in);
  const p = num(part);
  return (
    <Panel title={loan.frozen ? "Долг · заморозка" : `Кредит #${loan.id}`} tone={loan.frozen ? "red" : "violet"}>
      <div className="bk-loan-head">
        <span>банк <b>{loan.name}</b> · {loan.rate_label}/день</span>
        <b className="bk-debt">{fmt(loan.debt)}</b>
      </div>
      <Bar value={loan.paid} max={loan.paid + loan.debt} fill={loan.frozen ? "red" : "violet"} />
      <div className="bk-sub">погашено {fmt(loan.paid)} из {fmt(loan.paid + loan.debt)} · тело {fmt(loan.principal)}, проценты {fmt(loan.interest)}</div>
      {loan.frozen ? (
        <div className="bk-timer red"><Snowflake size={14} /> До удаления банды: <b>{countdown(frozenLeft)}</b></div>
      ) : (
        <div className={`bk-timer ${due < 86400 ? "red" : ""}`}><Lock size={14} /> До срока: <b>{due > 0 ? countdown(due) : "срок вышел"}</b></div>
      )}
      <div className="bk-repay">
        <input inputMode="numeric" value={part} placeholder="сумма" onChange={(e) => setPart(e.target.value.replace(/\D/g, ""))} />
        <button type="button" className="btn ghost small" disabled={busy || p <= 0} onClick={async () => { if (await run("/bank/repay", { loan_id: loan.id, amount: p })) setPart(""); }}>
          Погасить часть
        </button>
      </div>
      <button type="button" className={`btn ${loan.frozen ? "red" : "green"} block`} style={{ marginTop: 8 }} disabled={busy} onClick={() => run("/bank/repay", { loan_id: loan.id })}>
        Погасить всё · {fmt(loan.debt)}
      </button>
    </Panel>
  );
}

function LoansTab({ data, reload }: { data: BankHome; reload: () => void }) {
  if (!data.loans.length) {
    return <Panel title="Мои кредиты"><div className="bk-empty">Открытых кредитов нет. Возьми во вкладке «Банки».</div></Panel>;
  }
  return <>{data.loans.map((l) => <LoanCard key={l.id} loan={l} reload={reload} />)}</>;
}

function TermsFields({ rate, setRate, min, setMin, max, setMax, limits }: {
  rate: string; setRate: (v: string) => void; min: number; setMin: (v: number) => void; max: number; setMax: (v: number) => void; limits: BankHome["limits"];
}) {
  const days = Array.from({ length: limits.days_max - limits.days_min + 1 }, (_, i) => limits.days_min + i);
  return (
    <>
      <label className="bk-field">
        <span className="muted">Процент в день ({limits.rate_min * 100}–{limits.rate_max * 100}%)</span>
        <input inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value.replace(",", ".").replace(/[^\d.]/g, ""))} />
      </label>
      <div className="grid-2">
        <label className="bk-field">
          <span className="muted">Срок от, дн.</span>
          <select value={min} onChange={(e) => setMin(Number(e.target.value))}>{days.map((d) => <option key={d} value={d}>{d}</option>)}</select>
        </label>
        <label className="bk-field">
          <span className="muted">Срок до, дн.</span>
          <select value={max} onChange={(e) => setMax(Number(e.target.value))}>{days.map((d) => <option key={d} value={d}>{d}</option>)}</select>
        </label>
      </div>
    </>
  );
}

function MineTab({ data, reload }: { data: BankHome; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const b = data.my_bank;
  const [capital, setCapital] = useState("");
  const [rate, setRate] = useState(b ? String(+(b.rate * 100).toFixed(2)) : "5");
  const [min, setMin] = useState(b?.min_days ?? 3);
  const [max, setMax] = useState(b?.max_days ?? 14);
  const [move, setMove] = useState("");
  const [sheet, setSheet] = useState<"terms" | "close" | null>(null);
  const L = data.limits;
  const terms = { rate_percent: Number(rate) || 0, min_days: min, max_days: max };

  if (!b) {
    return (
      <Panel title="Создать банк" tone="gold">
        <div className="bk-note" style={{ marginBottom: 10 }}>
          Внеси капитал, поставь процент в день и срок. Проценты по кредитам капают в капитал банка, свободный капитал можно забрать в любой момент.
          Не вернувших к сроку бот наказывает сам: конфискация в твой банк, заморозка и удаление банды.
        </div>
        <label className="bk-field">
          <span className="muted">Капитал (от {fmt(L.min_capital)}, у тебя {fmt(data.coins)})</span>
          <input inputMode="numeric" value={capital} placeholder={String(L.min_capital)} onChange={(e) => setCapital(e.target.value.replace(/\D/g, ""))} />
        </label>
        <TermsFields rate={rate} setRate={setRate} min={min} setMin={setMin} max={max} setMax={setMax} limits={L} />
        <button type="button" className="btn gold block" style={{ marginTop: 10 }} disabled={busy || num(capital) < L.min_capital || min > max}
          onClick={() => run("/bank/create", { capital: num(capital), ...terms })}>
          <Plus size={16} /> Создать банк
        </button>
      </Panel>
    );
  }
  const m = num(move);
  return (
    <>
      <Panel title="Мой банк" tone="gold">
        <div className="bk-hero">
          <span>Свободный капитал</span>
          <b>{fmt(b.capital)}</b>
        </div>
        <StatRow label="Выдано сейчас" value={`${fmt(b.lent)} · ${b.open_loans} кред.`} />
        <StatRow label="Условия" value={`${b.rate_label}/день · ${b.min_days}–${b.max_days} дн.`} />
        <StatRow label="Заработано процентов" value={fmt(b.earned)} />
        <div className="bk-repay" style={{ marginTop: 10 }}>
          <input inputMode="numeric" value={move} placeholder="сумма" onChange={(e) => setMove(e.target.value.replace(/\D/g, ""))} />
          <button type="button" className="btn green small" disabled={busy || m <= 0} onClick={async () => { if (await run("/bank/deposit", { amount: m })) setMove(""); }}>
            <PiggyBank size={14} /> Внести
          </button>
          <button type="button" className="btn ghost small" disabled={busy || m <= 0} onClick={async () => { if (await run("/bank/withdraw", { amount: m })) setMove(""); }}>
            Забрать
          </button>
        </div>
        <div className="grid-2" style={{ marginTop: 10 }}>
          <button type="button" className="btn ghost small" onClick={() => setSheet("terms")}><Settings2 size={14} /> Условия</button>
          <button type="button" className="btn red small" onClick={() => setSheet("close")}><Trash2 size={14} /> Закрыть</button>
        </div>
      </Panel>
      <Panel title={`Должники · ${b.loans.length}`}>
        {b.loans.length === 0 && <div className="bk-empty">Кредитов пока не брали.</div>}
        {b.loans.map((l) => (
          <div key={l.id} className={`bk-debtor ${l.frozen ? "frozen" : ""}`}>
            <span>
              <b>{l.name}</b>
              <small>{l.frozen ? "заморожен · удаление через " + countdown(l.frozen_in) : l.due_in ? "срок через " + countdown(l.due_in) : "срок вышел"}</small>
            </span>
            <b className="mono">{fmt(l.debt)}</b>
          </div>
        ))}
      </Panel>
      {sheet === "terms" && (
        <Sheet title="Условия банка" onClose={() => setSheet(null)}>
          <div className="bk-note">Новые условия — только для новых кредитов, выданные живут по своим.</div>
          <TermsFields rate={rate} setRate={setRate} min={min} setMin={setMin} max={max} setMax={setMax} limits={L} />
          <button type="button" className="btn block" disabled={busy || min > max} onClick={async () => { if (await run("/bank/terms", terms)) setSheet(null); }}>
            Сохранить
          </button>
        </Sheet>
      )}
      {sheet === "close" && (
        <Sheet title="Закрыть банк?" onClose={() => setSheet(null)}>
          <div className="bk-note">Свободный капитал {fmt(b.capital)} вернётся на счёт. Закрыть можно, только когда все кредиты погашены.</div>
          <button type="button" className="btn red block" disabled={busy} onClick={async () => { if (await run("/bank/close")) setSheet(null); }}>
            Да, закрыть
          </button>
        </Sheet>
      )}
    </>
  );
}
