import { Banknote, Check, ChevronLeft, ChevronRight, FileSignature, Landmark, Lock, PiggyBank, Plus, Settings2, Snowflake, Trash2, UserMinus, UserPlus, Users, Wallet, X } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { BankHome, BankRow, BankTeam, LoanRow } from "../../types";
import { BackHeader, Bar, Chip, Panel, Screen, StatRow, countdown, fmt, useCountdown } from "../../components/ui";
import { Sheet } from "../../components/Sheet";
import { ROUTE_MORE } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import "./Bank.css";

// Кредиты — банки v2 (2026-11-14): заявка → банк одобряет → договор → подпись; фикс и почасовой; участники банка.
type Tab = "banks" | "loans" | "mine";
type Kind = "fixed" | "hourly";

const num = (v: string) => Math.floor(Number(v.replace(/\D/g, ""))) || 0;
const pct = (r: number | null | undefined) => (r == null ? "—" : `${+(r * 100).toFixed(2)}%`);
const KIND_NAME: Record<string, string> = { fixed: "фикс", hourly: "почасовой", daily: "в день" };

function kindsLabel(fixed: number | null, hourly: number | null): string {
  const parts = [];
  if (fixed != null) parts.push(`фикс +${pct(fixed)}`);
  if (hourly != null) parts.push(`${pct(hourly)}/ч`);
  return parts.join(" · ") || "—";
}

/** Кредиты — как «💳 Кредиты» в боте: банки, мои кредиты и договоры, мой банк. */
export function BankPage() {
  const [page, setPage] = useState(0);
  const { data, status, error, reload } = useApi<BankHome>(`/bank?page=${page}`);
  const [params] = useSearchParams();
  const initial = params.get("tab");
  const [tab, setTab] = useState<Tab>(initial === "loans" || initial === "mine" ? initial : "banks");
  const shown: Tab = data?.frozen ? "loans" : tab;
  const offers = data?.loans.filter((l) => l.status === "offered").length ?? 0;
  const apps = data?.team?.apps.length ?? 0;
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Кредиты" subtitle="банки игроков" to={ROUTE_MORE} />
          {data.frozen && (
            <Panel title="Банда заморожена" tone="red">
              <div className="bk-note">Долг не вернули к сроку. Всё заблокировано, весь доход уходит в долг, капает пеня. Погаси кредит — иначе рабство.</div>
            </Panel>
          )}
          <div className="grid-2">
            <Chip icon={<Wallet size={18} />} value={fmt(data.coins)} label="NHCoin на счёте" variant="gold" />
            <Chip icon={<Banknote size={18} />} value={fmt(data.loans.filter((l) => ["active", "frozen", "slave"].includes(l.status)).reduce((s, l) => s + l.debt, 0))}
              label="твой долг" variant="violet" />
          </div>
          {!data.frozen && (
            <div className="seg" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
              <button type="button" className={`pill ${shown === "banks" ? "on" : ""}`} onClick={() => setTab("banks")}>Банки</button>
              <button type="button" className={`pill ${shown === "loans" ? "on" : ""}`} onClick={() => setTab("loans")}>
                Мои кредиты{offers ? ` · ✍️${offers}` : data.loans.length ? ` · ${data.loans.length}` : ""}
              </button>
              <button type="button" className={`pill ${shown === "mine" ? "on" : ""}`} onClick={() => setTab("mine")}>Мой банк{apps ? ` · 📨${apps}` : ""}</button>
            </div>
          )}
          {shown === "banks" && <BanksTab data={data} page={page} setPage={setPage} reload={reload} />}
          {shown === "loans" && <LoansTab data={data} reload={reload} />}
          {shown === "mine" && <MineTab data={data} reload={reload} />}
        </div>
      )}
    </Screen>
  );
}

function BanksTab({ data, page, setPage, reload }: { data: BankHome; page: number; setPage: (p: number) => void; reload: () => void }) {
  const [pick, setPick] = useState<BankRow | null>(null);
  const L = data.limits;
  return (
    <>
      <Panel title="Банки игроков">
        <div className="bk-note" style={{ marginBottom: 10 }}>
          Подаёшь заявку → банк одобряет → подписываешь договор → деньги на счёте. 📌 Фикс — сумма + процент один раз. ⏱ Почасовой — процент каждый час на остаток.
          Не вернул к сроку: конфискация, заморозка на {L.freeze_days} дн. с пеней, потом рабство — {L.slave_share}% дохода банку.
        </div>
        {data.banks.length === 0 && <div className="bk-empty">Банков пока нет — создай свой во вкладке «Мой банк».</div>}
        {data.banks.map((b) => (
          <button key={b.id} type="button" className="bk-bank" onClick={() => setPick(b)}>
            <span className="ico-box"><Landmark size={18} /></span>
            <span className="bk-bank-main">
              <b>{b.owner}</b>
              <small>{b.min_days}–{b.max_days} дн. · пеня {b.penalty_rate ? `${pct(b.penalty_rate)}/ч` : "нет"}</small>
            </span>
            <span className="bk-bank-side">
              <b className="bk-rate">{kindsLabel(b.fixed_rate, b.hourly_rate)}</b>
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
      {pick && <ApplySheet bank={pick} minLoan={L.min_loan} onClose={() => setPick(null)} reload={reload} />}
    </>
  );
}

function ApplySheet({ bank, minLoan, onClose, reload }: { bank: BankRow; minLoan: number; onClose: () => void; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const kinds: Kind[] = (["fixed", "hourly"] as Kind[]).filter((k) => (k === "fixed" ? bank.fixed_rate : bank.hourly_rate) != null);
  const [kind, setKind] = useState<Kind>(kinds[0] ?? "fixed");
  const [amount, setAmount] = useState("");
  const [days, setDays] = useState(bank.min_days);
  const rate = (kind === "fixed" ? bank.fixed_rate : bank.hourly_rate) ?? 0;
  const a = num(amount);
  const valid = a >= minLoan && a <= bank.capital;
  const dayList = Array.from({ length: bank.max_days - bank.min_days + 1 }, (_, i) => bank.min_days + i);
  const total = kind === "fixed" ? a + Math.max(1, Math.round(a * rate)) : a + Math.max(1, Math.round(a * rate)) * days * 24;
  const submit = async () => {
    if (await run("/bank/apply", { bank_id: bank.id, kind, amount: a, days })) onClose();
  };
  return (
    <Sheet title={`Банк ${bank.owner}`} onClose={onClose}>
      {kinds.length > 1 && (
        <div className="seg" style={{ gridTemplateColumns: "1fr 1fr" }}>
          {kinds.map((k) => (
            <button key={k} type="button" className={`pill ${kind === k ? "on" : ""}`} onClick={() => setKind(k)}>
              {k === "fixed" ? `📌 Фикс +${pct(bank.fixed_rate)}` : `⏱ ${pct(bank.hourly_rate)} в час`}
            </button>
          ))}
        </div>
      )}
      <StatRow label="Можно взять" value={`${fmt(minLoan)} – ${fmt(bank.capital)}`} />
      <label className="bk-field">
        <span className="muted">Сумма</span>
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
        {dayList.map((d) => <button key={d} type="button" className={`pill ${days === d ? "on" : ""}`} onClick={() => setDays(d)}>{d}</button>)}
      </div>
      {valid && (
        <div className="bk-calc">
          <div><span>{kind === "fixed" ? "Проценты (один раз)" : "Проценты в час"}</span><b>{fmt(Math.max(1, Math.round(a * rate)))}</b></div>
          <div><span>{kind === "fixed" ? "Вернуть" : "Если гасить в последний час"}</span><b className="bk-gold">{fmt(total)}</b></div>
          <small>Банк рассмотрит заявку и пришлёт договор. Деньги — после подписи.</small>
        </div>
      )}
      <button type="button" className="btn gold block" disabled={busy || !valid} onClick={() => void submit()}>
        <FileSignature size={16} /> Подать заявку
      </button>
    </Sheet>
  );
}

function ContractCard({ loan, reload }: { loan: LoanRow; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const left = useCountdown(loan.offer_in);
  const total = loan.kind === "fixed" ? loan.amount + Math.max(1, Math.round(loan.amount * loan.rate)) : 0;
  return (
    <Panel title={`Договор №${loan.id}`} tone="gold">
      <div className="bk-contract">
        <div className="bk-contract-title">🏦 КРЕДИТНЫЙ ДОГОВОР · {loan.kind === "fixed" ? "фиксированная ставка" : "почасовая ставка"}</div>
        <StatRow label="Банк" value={loan.name} />
        <StatRow label="Сумма" value={fmt(loan.amount)} />
        <StatRow label="Ставка" value={loan.kind === "fixed" ? `+${pct(loan.rate)} один раз → ${fmt(total)}` : `${pct(loan.rate)} в час на остаток`} />
        <StatRow label="Срок" value={`${loan.days} дн.`} />
        <StatRow label="Пеня за просрочку" value={loan.penalty_rate ? `${pct(loan.penalty_rate)} в час` : "нет"} />
        {loan.terms && <div className="bk-terms"><b>Условия банка</b>{loan.terms}</div>}
        <div className="bk-note" style={{ marginTop: 8 }}>
          Не вернул к сроку: конфискация (монеты → статисты → здания), заморозка с пеней, потом рабство — 90% дохода банку до полного погашения.
        </div>
      </div>
      <div className="bk-timer"><Lock size={14} /> Подписать до: <b>{countdown(left)}</b></div>
      <div className="grid-2" style={{ marginTop: 10 }}>
        <button type="button" className="btn ghost" disabled={busy} onClick={() => run("/bank/decline", { loan_id: loan.id })}><X size={15} />Отказаться</button>
        <button type="button" className="btn gold" disabled={busy || left <= 0} onClick={() => run("/bank/sign", { loan_id: loan.id })}><FileSignature size={15} />Подписать</button>
      </div>
    </Panel>
  );
}

function LoanCard({ loan, reload }: { loan: LoanRow; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const [part, setPart] = useState("");
  const due = useCountdown(loan.due_in);
  const frozenLeft = useCountdown(loan.frozen_in);
  const p = num(part);
  const tone = loan.status === "frozen" || loan.status === "slave" ? "red" : "violet";
  const title = loan.status === "frozen" ? "Долг · заморозка" : loan.status === "slave" ? "Долг · рабство" : `Кредит #${loan.id}`;
  return (
    <Panel title={title} tone={tone}>
      <div className="bk-loan-head">
        <span>банк <b>{loan.name}</b> · {KIND_NAME[loan.kind] ?? loan.kind} {pct(loan.rate)}</span>
        <b className="bk-debt">{fmt(loan.debt)}</b>
      </div>
      <Bar value={loan.paid} max={loan.paid + loan.debt} fill={tone === "red" ? "red" : "violet"} />
      <div className="bk-sub">
        погашено {fmt(loan.paid)} · тело {fmt(loan.principal)}, проценты {fmt(loan.interest)}{loan.penalty ? `, пеня ${fmt(loan.penalty)}` : ""}
      </div>
      {loan.status === "frozen" && <div className="bk-timer red"><Snowflake size={14} /> До рабства: <b>{countdown(frozenLeft)}</b></div>}
      {loan.status === "slave" && <div className="bk-timer red"><Lock size={14} /> 90% дохода уходит банку, пока долг не закрыт</div>}
      {loan.status === "active" && (
        <div className={`bk-timer ${due < 86400 ? "red" : ""}`}><Lock size={14} /> До срока: <b>{due > 0 ? countdown(due) : "срок вышел"}</b></div>
      )}
      <div className="bk-repay">
        <input inputMode="numeric" value={part} placeholder="сумма" onChange={(e) => setPart(e.target.value.replace(/\D/g, ""))} />
        <button type="button" className="btn ghost small" disabled={busy || p <= 0} onClick={async () => { if (await run("/bank/repay", { loan_id: loan.id, amount: p })) setPart(""); }}>
          Погасить часть
        </button>
      </div>
      <button type="button" className={`btn ${tone === "red" ? "red" : "green"} block`} style={{ marginTop: 8 }} disabled={busy}
        onClick={() => run("/bank/repay", { loan_id: loan.id })}>
        Погасить всё · {fmt(loan.debt)}
      </button>
    </Panel>
  );
}

function LoansTab({ data, reload }: { data: BankHome; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const offered = data.loans.filter((l) => l.status === "offered");
  const pending = data.loans.filter((l) => l.status === "pending");
  const open = data.loans.filter((l) => ["active", "frozen", "slave"].includes(l.status));
  if (!data.loans.length) return <Panel title="Мои кредиты"><div className="bk-empty">Кредитов и заявок нет. Подай заявку во вкладке «Банки».</div></Panel>;
  return (
    <>
      {offered.map((l) => <ContractCard key={l.id} loan={l} reload={reload} />)}
      {pending.length > 0 && (
        <Panel title="Заявки">
          {pending.map((l) => (
            <div key={l.id} className="bk-debtor">
              <span><b>банк {l.name}</b><small>{fmt(l.amount)} на {l.days} дн. · {KIND_NAME[l.kind]} · ждёт ответа банка</small></span>
              <button type="button" className="btn ghost small" disabled={busy} onClick={() => run("/bank/cancel", { loan_id: l.id })}>Отозвать</button>
            </div>
          ))}
        </Panel>
      )}
      {open.map((l) => <LoanCard key={l.id} loan={l} reload={reload} />)}
    </>
  );
}

function TermsFields({ t, set, limits }: { t: TermsState; set: (t: TermsState) => void; limits: BankHome["limits"] }) {
  const days = Array.from({ length: limits.days_max - limits.days_min + 1 }, (_, i) => limits.days_min + i);
  return (
    <>
      <div className="bk-kind-row">
        <label className="bk-toggle"><input type="checkbox" checked={t.fixedOn} onChange={(e) => set({ ...t, fixedOn: e.target.checked })} /> 📌 Фикс</label>
        <input inputMode="decimal" disabled={!t.fixedOn} value={t.fixed} onChange={(e) => set({ ...t, fixed: e.target.value.replace(",", ".").replace(/[^\d.]/g, "") })} />
        <span className="muted">% один раз (до {limits.fixed_max * 100}%)</span>
      </div>
      <div className="bk-kind-row">
        <label className="bk-toggle"><input type="checkbox" checked={t.hourlyOn} onChange={(e) => set({ ...t, hourlyOn: e.target.checked })} /> ⏱ Почасовой</label>
        <input inputMode="decimal" disabled={!t.hourlyOn} value={t.hourly} onChange={(e) => set({ ...t, hourly: e.target.value.replace(",", ".").replace(/[^\d.]/g, "") })} />
        <span className="muted">% в час (до {limits.hourly_max * 100}%)</span>
      </div>
      <div className="bk-kind-row">
        <span className="bk-toggle">⚖️ Пеня</span>
        <input inputMode="decimal" value={t.penalty} onChange={(e) => set({ ...t, penalty: e.target.value.replace(",", ".").replace(/[^\d.]/g, "") })} />
        <span className="muted">% в час в заморозку (до {limits.penalty_max * 100}%)</span>
      </div>
      <div className="grid-2">
        <label className="bk-field"><span className="muted">Срок от, дн.</span>
          <select value={t.min} onChange={(e) => set({ ...t, min: Number(e.target.value) })}>{days.map((d) => <option key={d} value={d}>{d}</option>)}</select></label>
        <label className="bk-field"><span className="muted">Срок до, дн.</span>
          <select value={t.max} onChange={(e) => set({ ...t, max: Number(e.target.value) })}>{days.map((d) => <option key={d} value={d}>{d}</option>)}</select></label>
      </div>
    </>
  );
}

interface TermsState { fixedOn: boolean; fixed: string; hourlyOn: boolean; hourly: string; penalty: string; min: number; max: number }

function termsFrom(team: BankTeam | null): TermsState {
  const p = (r: number | null | undefined, d: string) => (r == null ? d : String(+(r * 100).toFixed(3)));
  return {
    fixedOn: team ? team.fixed_rate != null : true, fixed: p(team?.fixed_rate, "20"),
    hourlyOn: team ? team.hourly_rate != null : true, hourly: p(team?.hourly_rate, "0.5"),
    penalty: team ? String(+(team.penalty_rate * 100).toFixed(3)) : "1", min: team?.min_days ?? 1, max: team?.max_days ?? 7,
  };
}

function termsBody(t: TermsState) {
  return {
    fixed_percent: t.fixedOn ? Number(t.fixed) || 0 : null, hourly_percent: t.hourlyOn ? Number(t.hourly) || 0 : null,
    penalty_percent: Number(t.penalty) || 0, min_days: t.min, max_days: t.max,
  };
}

function MineTab({ data, reload }: { data: BankHome; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const team = data.team;
  const L = data.limits;
  const [capital, setCapital] = useState("");
  const [terms, setTerms] = useState<TermsState>(termsFrom(team));
  const [move, setMove] = useState("");
  const [member, setMember] = useState("");
  const [sheet, setSheet] = useState<"terms" | "close" | null>(null);
  const [approve, setApprove] = useState<LoanRow | null>(null);
  const [approveText, setApproveText] = useState("");

  if (!team) {
    return (
      <Panel title="Создать банк" tone="gold">
        <div className="bk-note" style={{ marginBottom: 10 }}>
          Внеси капитал и задай условия. Проценты и пеня капают в капитал банка. Можно позвать до {L.members_max} участников — они пополняют капитал и одобряют заявки.
        </div>
        <label className="bk-field">
          <span className="muted">Капитал (от {fmt(L.min_capital)}, у тебя {fmt(data.coins)})</span>
          <input inputMode="numeric" value={capital} placeholder={String(L.min_capital)} onChange={(e) => setCapital(e.target.value.replace(/\D/g, ""))} />
        </label>
        <TermsFields t={terms} set={setTerms} limits={L} />
        <button type="button" className="btn gold block" style={{ marginTop: 10 }} disabled={busy || num(capital) < L.min_capital || terms.min > terms.max}
          onClick={() => run("/bank/create", { capital: num(capital), ...termsBody(terms) })}>
          <Plus size={16} /> Создать банк
        </button>
      </Panel>
    );
  }
  const m = num(move);
  return (
    <>
      <Panel title={team.is_owner ? "Мой банк" : `Банк ${team.owner}`} tone="gold">
        <div className="bk-hero"><span>Свободный капитал</span><b>{fmt(team.capital)}</b></div>
        <StatRow label="Выдано сейчас" value={`${fmt(team.lent)} · ${team.open_loans} кред.`} />
        <StatRow label="В резерве под договоры" value={fmt(team.reserved)} />
        <StatRow label="Условия" value={`${kindsLabel(team.fixed_rate, team.hourly_rate)} · ${team.min_days}–${team.max_days} дн.`} />
        <StatRow label="Пеня" value={team.penalty_rate ? `${pct(team.penalty_rate)}/ч` : "нет"} />
        <StatRow label="Заработано" value={fmt(team.earned)} />
        <div className="bk-repay" style={{ marginTop: 10, gridTemplateColumns: team.is_owner ? undefined : "minmax(0, 1fr) auto" }}>
          <input inputMode="numeric" value={move} placeholder="сумма" onChange={(e) => setMove(e.target.value.replace(/\D/g, ""))} />
          <button type="button" className="btn green small" disabled={busy || m <= 0} onClick={async () => { if (await run("/bank/deposit", { amount: m })) setMove(""); }}>
            <PiggyBank size={14} /> Внести
          </button>
          {team.is_owner && (
            <button type="button" className="btn ghost small" disabled={busy || m <= 0} onClick={async () => { if (await run("/bank/withdraw", { amount: m })) setMove(""); }}>
              Забрать
            </button>
          )}
        </div>
        {team.is_owner ? (
          <div className="grid-2" style={{ marginTop: 10 }}>
            <button type="button" className="btn ghost small" onClick={() => { setTerms(termsFrom(team)); setSheet("terms"); }}><Settings2 size={14} /> Условия</button>
            <button type="button" className="btn red small" onClick={() => setSheet("close")}><Trash2 size={14} /> Закрыть</button>
          </div>
        ) : (
          <button type="button" className="btn ghost small block" style={{ marginTop: 10 }} disabled={busy} onClick={() => run("/bank/leave")}>Выйти из банка</button>
        )}
      </Panel>

      <Panel title={`Заявки · ${team.apps.length}`} tone="green">
        {team.apps.length === 0 && <div className="bk-empty">Новых заявок нет.</div>}
        {team.apps.map((l) => (
          <div key={l.id} className="bk-app">
            <div className="bk-debtor" style={{ borderBottom: 0, paddingBottom: 4 }}>
              <span><b>{l.name}</b><small>{KIND_NAME[l.kind]} {pct(l.rate)} · на {l.days} дн.</small></span>
              <b className="mono">{fmt(l.amount)}</b>
            </div>
            <div className="grid-2">
              <button type="button" className="btn ghost small" disabled={busy} onClick={() => run("/bank/reject", { loan_id: l.id })}><X size={14} />Отклонить</button>
              <button type="button" className="btn green small" disabled={busy} onClick={() => { setApprove(l); setApproveText(""); }}><Check size={14} />Одобрить</button>
            </div>
          </div>
        ))}
      </Panel>

      <Panel title={`Должники · ${team.loans.length}`}>
        {team.loans.length === 0 && <div className="bk-empty">Выданных кредитов нет.</div>}
        {team.loans.map((l) => (
          <div key={l.id} className={`bk-debtor ${l.status === "frozen" || l.status === "slave" ? "frozen" : ""}`}>
            <span>
              <b>{l.name}</b>
              <small>{l.status === "frozen" ? "🧊 заморожен" : l.status === "slave" ? "⛓ в рабстве — 90% дохода в банк" : `срок через ${countdown(l.due_in)}`}</small>
            </span>
            <b className="mono">{fmt(l.debt)}</b>
          </div>
        ))}
      </Panel>

      {team.is_owner && (
        <Panel title={`Участники · ${team.members.length}/${L.members_max}`}>
          <div className="bk-note" style={{ marginBottom: 8 }}>Пополняют капитал и одобряют заявки. Забрать деньги, менять условия и закрыть банк — только ты.</div>
          {team.members.map((u) => (
            <div key={u.id} className="bk-debtor">
              <span><b><Users size={13} /> {u.name}</b></span>
              <button type="button" className="btn ghost small" disabled={busy} onClick={() => run("/bank/members/remove", { user_id: u.id })}><UserMinus size={14} /></button>
            </div>
          ))}
          {team.members.length < L.members_max && (
            <div className="bk-repay" style={{ gridTemplateColumns: "minmax(0, 1fr) auto" }}>
              <input value={member} placeholder="@ник игрока" onChange={(e) => setMember(e.target.value)} />
              <button type="button" className="btn small" disabled={busy || member.trim().length < 2} onClick={async () => { if (await run("/bank/members/add", { username: member })) setMember(""); }}>
                <UserPlus size={14} /> Добавить
              </button>
            </div>
          )}
        </Panel>
      )}

      {approve && (
        <Sheet title={`Одобрить заявку #${approve.id}`} onClose={() => setApprove(null)}>
          <StatRow label="Заёмщик" value={approve.name} />
          <StatRow label="Сумма" value={fmt(approve.amount)} />
          <StatRow label="Вид" value={`${KIND_NAME[approve.kind]} ${pct(approve.rate)}`} />
          <label className="bk-field">
            <span className="muted">Свои условия в договор (необязательно)</span>
            <textarea rows={4} maxLength={500} value={approveText} onChange={(e) => setApproveText(e.target.value)} placeholder="Например: верни раньше — скидка 5%" />
          </label>
          <button type="button" className="btn green block" style={{ marginTop: 10 }} disabled={busy}
            onClick={async () => { if (await run("/bank/approve", { loan_id: approve.id, terms: approveText || null })) setApprove(null); }}>
            <FileSignature size={15} /> Одобрить и отправить договор
          </button>
        </Sheet>
      )}
      {sheet === "terms" && (
        <Sheet title="Условия банка" onClose={() => setSheet(null)}>
          <div className="bk-note">Новые условия — только для новых заявок.</div>
          <TermsFields t={terms} set={setTerms} limits={L} />
          <button type="button" className="btn block" style={{ marginTop: 10 }} disabled={busy || terms.min > terms.max}
            onClick={async () => { if (await run("/bank/terms", termsBody(terms))) setSheet(null); }}>Сохранить</button>
        </Sheet>
      )}
      {sheet === "close" && (
        <Sheet title="Закрыть банк?" onClose={() => setSheet(null)}>
          <div className="bk-note">Свободный капитал {fmt(team.capital)} вернётся на счёт. Закрыть можно, когда нет кредитов и заявок.</div>
          <button type="button" className="btn red block" style={{ marginTop: 10 }} disabled={busy} onClick={async () => { if (await run("/bank/close")) setSheet(null); }}>Да, закрыть</button>
        </Sheet>
      )}
    </>
  );
}
