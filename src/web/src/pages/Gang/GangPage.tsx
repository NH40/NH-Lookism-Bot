import { ArrowDownUp, Crown, Dices, Minus, PenLine, Plus, Shield, Sparkles, Swords, Ticket, Trash2, UserPlus, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { imgUrl } from "../../api";
import type { GangData, RollManyResult, RollResult, Squad } from "../../types";
import { BackHeader, Bar, Panel, Screen, countdown, fmt, useCountdown } from "../../components/ui";
import { ROUTE_MAP } from "../../constants/constants";
import { useAction, useApi } from "../../hooks/useApi";
import { Sheet } from "../../components/Sheet";
import "../../styles/game-screens.css";
import "./Gang.css";

// Страница банды (переделана с нуля 2026-11-14): шапка-статус + три вкладки вместо длинной ленты.
type Tab = "army" | "recruit" | "manage";

// Классические ранги F…S — по ступеням; всё, что выше S (SS, X, Z, YY, DXR, ∞…), — «топ».
function rankTone(rank: string): string {
  if (/^[FED][+-]?$/.test(rank)) return "";
  if (/^C[+-]?$/.test(rank)) return "low";
  if (/^B[+-]?$/.test(rank)) return "mid";
  if (/^(A|S[+-]?$)/.test(rank)) return "hi";
  return "top";
}

function rankShort(rank: string): string {
  if (rank.toLowerCase().startsWith("inf")) return "∞";
  return rank.length > 3 ? rank.slice(0, 3) : rank;
}

const SQUADS_SHOWN = 15;

export function GangPage() {
  const { data, status, error, reload } = useApi<GangData>("/gang");
  const { hash } = useLocation();
  const fromHash = (h: string): Tab => (h === "#recruit" ? "recruit" : h === "#manage" ? "manage" : "army");
  const [tab, setTab] = useState<Tab>(fromHash(hash));
  const [renameOpen, setRenameOpen] = useState(false);
  useEffect(() => {
    if (hash) setTab(fromHash(hash));
  }, [hash]);

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Банда" backLabel="Карта" to={ROUTE_MAP} />
          <Hero data={data} onRename={() => setRenameOpen(true)} />
          <div className="seg" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
            <button type="button" className={`pill ${tab === "army" ? "on" : ""}`} onClick={() => setTab("army")}><Users size={15} />Армия</button>
            <button type="button" className={`pill ${tab === "recruit" ? "on" : ""}`} onClick={() => setTab("recruit")}><UserPlus size={15} />Вербовка</button>
            <button type="button" className={`pill ${tab === "manage" ? "on" : ""}`} onClick={() => setTab("manage")}><PenLine size={15} />Управление</button>
          </div>
          {tab === "army" && <ArmyTab data={data} reload={reload} />}
          {tab === "recruit" && <RecruitTab data={data} reload={reload} />}
          {tab === "manage" && <ManageTab data={data} reload={reload} onRename={() => setRenameOpen(true)} />}
        </div>
      )}
      {data && renameOpen && <RenameSheet data={data} reload={reload} onClose={() => setRenameOpen(false)} />}
    </Screen>
  );
}

/** Шапка: название, фаза, общая мощь и баланс лагерей. */
function Hero({ data, onRename }: { data: GangData; onRename: () => void }) {
  const total = data.attack.power + data.defense.power;
  const attackShare = total > 0 ? (data.attack.power / total) * 100 : 50;
  const fighters = data.attack.quantity + data.defense.quantity;
  return (
    <section className="gg-hero">
      <div className="gg-hero-top">
        <span className="gg-emblem"><Crown size={22} /></span>
        <div className="gg-hero-name">
          <small>◆ БАНДА</small>
          <b>{data.name}</b>
        </div>
        <button type="button" className="gg-icon-btn" onClick={onRename} aria-label="Переименовать банду"><PenLine size={16} /></button>
      </div>
      <div className="gg-hero-stats">
        <div><small>общая мощь</small><b className="gg-cyan">{fmt(total)}</b></div>
        <div><small>бойцов</small><b>{fmt(fighters)}</b></div>
        <div><small>уники в армии</small><b className="gg-gold">{fmt(data.cards_quantity)}</b></div>
      </div>
      <div className="gg-split" aria-label="Баланс атаки и защиты">
        <div className="gg-split-atk" style={{ width: `${attackShare}%` }} />
        <div className="gg-split-def" />
      </div>
      <div className="gg-split-legend">
        <span className="atk"><Swords size={12} />атака {fmt(data.attack.power)}</span>
        <span className="def">защита {fmt(data.defense.power)}<Shield size={12} /></span>
      </div>
    </section>
  );
}

function ArmyTab({ data, reload }: { data: GangData; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const [from, setFrom] = useState<"attack" | "defense">("attack");
  const [sort, setSort] = useState<"power" | "count">("power");
  const [all, setAll] = useState(false);
  const squads = useMemo(() => {
    const list = [...data.squads];
    list.sort((a, b) => (sort === "power" ? b.unit_power - a.unit_power : b.total - a.total));
    return list;
  }, [data.squads, sort]);
  const shown = all ? squads : squads.slice(0, SQUADS_SHOWN);
  const to = from === "attack" ? "защиту" : "атаку";
  return (
    <>
      <Panel title="Лагеря">
        <div className="gg-camps">
          <CampCard kind="attack" active={from === "attack"} quantity={data.attack.quantity} power={data.attack.power} onClick={() => setFrom("attack")} />
          <button type="button" className="gg-swap" onClick={() => setFrom(from === "attack" ? "defense" : "attack")} aria-label="Поменять направление">
            <ArrowDownUp size={16} />
          </button>
          <CampCard kind="defense" active={from === "defense"} quantity={data.defense.quantity} power={data.defense.power} onClick={() => setFrom("defense")} />
        </div>
        <div className="gg-move-label">Перевести из {from === "attack" ? "атаки" : "защиты"} в {to}</div>
        <div className="gg-move" style={{ gridTemplateColumns: `repeat(${data.move_percents.length}, minmax(0, 1fr))` }}>
          {data.move_percents.map((p) => (
            <button key={p} type="button" className="pill" disabled={busy} onClick={() => run("/gang/move", { from_camp: from, percent: p })}>
              {p === 100 ? "всех" : `${p}%`}
            </button>
          ))}
        </div>
      </Panel>

      <Panel title={`Отряды · ${data.squads.length}`}>
        <div className="seg gg-sort" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <button type="button" className={`pill ${sort === "power" ? "on" : ""}`} onClick={() => setSort("power")}>сильнейшие</button>
          <button type="button" className={`pill ${sort === "count" ? "on" : ""}`} onClick={() => setSort("count")}>многочисленные</button>
        </div>
        {squads.length === 0 && <div className="gg-empty">Отрядов пока нет — заверби статистов во вкладке «Вербовка».</div>}
        {shown.map((sq) => <SquadRow key={`${sq.rank}-${sq.stars}-${sq.training_level}-${sq.school}-${sq.school_level}`} sq={sq} />)}
        {squads.length > SQUADS_SHOWN && (
          <button className="btn ghost small block" type="button" style={{ marginTop: 10 }} onClick={() => setAll(!all)}>
            {all ? "Свернуть" : `Показать все (${squads.length})`}
          </button>
        )}
      </Panel>
    </>
  );
}

function CampCard({ kind, active, quantity, power, onClick }: { kind: "attack" | "defense"; active: boolean; quantity: number; power: number; onClick: () => void }) {
  return (
    <button type="button" className={`gg-camp ${kind} ${active ? "on" : ""}`} onClick={onClick}>
      <span className="gg-camp-title">{kind === "attack" ? <Swords size={14} /> : <Shield size={14} />}{kind === "attack" ? "Атака" : "Защита"}</span>
      <b>{fmt(quantity)}</b>
      <small>мощь {fmt(power)}</small>
    </button>
  );
}

function SquadRow({ sq }: { sq: Squad }) {
  const atk = sq.total > 0 ? (sq.attack / sq.total) * 100 : 0;
  return (
    <div className="gg-sq">
      <span className={`gg-rank ${rankTone(sq.rank)}`}>{rankShort(sq.rank)}</span>
      <div className="gg-sq-main">
        <div className="gg-sq-name">
          {sq.rank}
          {sq.stars > 0 && <span className="gg-stars">{"★".repeat(Math.min(sq.stars, 5))}</span>}
          {sq.training_level > 0 && <span className="gg-tag">ур. {sq.training_level}</span>}
          {sq.school && <span className="gg-tag school">{sq.school}{sq.school_level ? ` ${sq.school_level}` : ""}</span>}
        </div>
        <div className="gg-sq-split"><i style={{ width: `${atk}%` }} /></div>
        <div className="gg-sq-sub">⚔ {fmt(sq.attack)} · 🛡 {fmt(sq.defense)} · мощь бойца {fmt(sq.unit_power)}</div>
      </div>
      <b className="gg-sq-total">×{fmt(sq.total)}</b>
    </div>
  );
}

function RecruitTab({ data, reload }: { data: GangData; reload: () => void }) {
  const { run, busy } = useAction(reload);
  const cd = useCountdown(data.recruit_cooldown_seconds);
  const nextTicket = useCountdown(data.tickets.next_in_seconds ?? 0);
  const [count, setCount] = useState(Math.max(1, Math.min(10, data.tickets.count)));
  const [reveal, setReveal] = useState<RollResult | null>(null);
  const [many, setMany] = useState<RollManyResult | null>(null);
  const roll = async () => {
    const r = await run("/gacha/roll");
    if (r) setReveal(r as never);
  };
  const rollMany = async () => {
    const r = await run("/gacha/roll-many", { count });
    if (r) setMany(r as never);
  };
  const t = data.tickets;
  return (
    <>
      <Panel title="Статисты" tone="green">
        <div className="gg-rec-info">
          <div><small>влияние</small><b>{fmt(data.influence)}</b></div>
          <div><small>ранг до</small><b>{data.recruit_ceiling_rank}</b></div>
          <div><small>следующая</small><b className={cd > 0 ? "" : "gg-green"}>{cd > 0 ? countdown(cd) : "готово"}</b></div>
        </div>
        <div className="grid-2">
          <button className="btn green block" type="button" disabled={busy || cd > 0} onClick={() => run("/recruit/extra")}>
            <Users size={16} />Толпа · {fmt(data.recruit_crowd)}
          </button>
          <button className="btn violet block" type="button" disabled={busy || cd > 0} onClick={() => run("/recruit/extra", { select: true })}>
            <Sparkles size={16} />Отбор · {fmt(data.recruit_select)}
          </button>
        </div>
        <div className="gg-hint">Толпа — больше бойцов любых рангов. Отбор — меньше, но только сильные ранги.</div>
      </Panel>

      <Panel title="Уники" tone="gold">
        <div className="gg-tickets">
          <Ticket size={18} />
          <div style={{ flex: 1 }}>
            <div className="row"><span className="muted" style={{ fontSize: 12, fontWeight: 700 }}>тикеты</span><b className="mono">{t.count} / {t.cap}</b></div>
            <Bar value={t.count} max={t.cap} fill="gold" />
            {t.next_in_seconds ? <small className="muted">+1 тикет через {countdown(nextTicket)}</small> : null}
          </div>
        </div>
        <button className="btn gold block" type="button" disabled={busy || t.count <= 0} onClick={roll}>
          <Dices size={16} />Крутка уника
        </button>
        <div className="gg-many">
          <button type="button" className="btn ghost small" disabled={count <= 1} onClick={() => setCount(Math.max(1, count - 10))}><Minus size={14} /></button>
          <b className="mono">{count}</b>
          <button type="button" className="btn ghost small" onClick={() => setCount(Math.min(Math.max(1, t.count), count + 10))}><Plus size={14} /></button>
          <button type="button" className="btn ghost small" disabled={t.count <= 0} onClick={() => setCount(Math.max(1, t.count))}>все</button>
          <button type="button" className="btn gold small" disabled={busy || t.count <= 0} onClick={rollMany}>Открыть {count}</button>
        </div>
      </Panel>

      {many && (
        <Sheet title={`Открыто тикетов: ${fmt(many.count)}`} onClose={() => setMany(null)}>
          <div className="gg-rec-info">
            <div><small>новых</small><b className="gg-green">{many.new}</b></div>
            <div><small>тикетов</small><b>{many.tickets}/{many.tickets_cap}</b></div>
            <div><small>вернулось</small><b>{many.free}</b></div>
          </div>
          <div className="gg-rarities">
            {many.rarities.map((r) => <span key={r.rarity}>{r.label}: <b>{fmt(r.count)}</b></span>)}
          </div>
          {many.count < many.requested && <div className="gg-hint">Тикеты закончились — открыто, сколько хватило.</div>}
          <div className="gg-cards">
            {many.cards.map((c, i) => (
              <div key={`${c.code}-${i}`} className="gg-card">
                {c.image && <img src={imgUrl(c.image, 160)} alt={c.name} loading="lazy" />}
                {c.is_new && <span className="gg-new">NEW</span>}
                {c.count > 1 && <span className="gg-copies">×{fmt(c.count)}</span>}
                <div className="gg-card-name">{c.name}</div>
              </div>
            ))}
          </div>
          <div className="grid-2" style={{ marginTop: 14 }}>
            <button className="btn ghost" type="button" onClick={() => setMany(null)}>Закрыть</button>
            <button className="btn gold" type="button" disabled={busy || many.tickets <= 0} onClick={rollMany}>Ещё {Math.min(count, many.tickets)}</button>
          </div>
        </Sheet>
      )}
      {reveal && (
        <Sheet title="Новый уник" onClose={() => setReveal(null)}>
          <div className="reveal-art">{reveal.card.image && <img src={imgUrl(reveal.card.image, 480)} alt={reveal.card.name} />}</div>
          <div style={{ textAlign: "center" }}>
            <div className="disp" style={{ fontSize: 18 }}>{reveal.card.name}</div>
            <div style={{ color: "var(--gold-2)", fontSize: 12, fontWeight: 800, margin: "4px 0" }}>{reveal.card.rarity_label}</div>
            <div className="muted" style={{ fontSize: 12, fontWeight: 700 }}>
              мощь {fmt(reveal.card.power)} · копий у тебя: {reveal.copies}{reveal.free ? " · тикет вернулся" : ""}
            </div>
          </div>
          {reveal.absolute_perk && <div className="reveal-perk">♾ {reveal.absolute_perk}</div>}
          {reveal.skills.map((g) => g.skills.length > 0 && (
            <div key={g.position} className="reveal-skills">
              <div className="reveal-skills-title">Навыки · {g.label} · {g.skills.length}</div>
              {g.skills.map((sk) => (
                <div key={sk.name} className="reveal-skill"><b>{sk.name}</b> <span className="muted">· {sk.kind_label}</span><div className="muted">{sk.text}</div></div>
              ))}
            </div>
          ))}
          <div className="grid-2" style={{ marginTop: 14 }}>
            <button className="btn ghost" type="button" onClick={() => setReveal(null)}>Закрыть</button>
            <button className="btn gold" type="button" disabled={busy || reveal.tickets <= 0} onClick={roll}>Ещё ({reveal.tickets})</button>
          </div>
        </Sheet>
      )}
    </>
  );
}

function ManageTab({ data, reload, onRename }: { data: GangData; reload: () => void; onRename: () => void }) {
  const { run, busy } = useAction(reload);
  const [deleteSeconds, setDeleteSeconds] = useState(0);
  const deleteLeft = useCountdown(deleteSeconds);
  const renameLeft = useCountdown(data.rename_cooldown_seconds ?? 0);
  const askDelete = async () => {
    const r = await run("/gang/delete/request");
    if (r) setDeleteSeconds(Number(r.seconds) || 0);
  };
  return (
    <>
      <Panel title="Название">
        <div className="gg-manage-row">
          <div>
            <b>{data.name}</b>
            <small>{fmt(data.rename_price ?? 0)} NHCoin · раз в неделю{renameLeft > 0 ? ` · через ${countdown(renameLeft)}` : ""}</small>
          </div>
          <button type="button" className="btn small" disabled={renameLeft > 0} onClick={onRename}><PenLine size={14} />Сменить</button>
        </div>
      </Panel>
      <Panel title="Опасная зона" tone="red">
        <div className="gg-hint" style={{ marginTop: 0, marginBottom: 10 }}>
          Сбросится весь прогресс: банда, районы и бизнес на них, статисты, уники, характеристики, мастерство, NHCoin.
          Останутся потенциал, пробуждение, родословная и талант.
        </div>
        <button className="btn red block" type="button" disabled={busy} onClick={askDelete}><Trash2 size={16} />Удалить банду</button>
      </Panel>
      {deleteSeconds > 0 && deleteLeft > 0 && (
        <Sheet title="Удалить банду?" onClose={() => setDeleteSeconds(0)}>
          <div className="gg-hint" style={{ marginBottom: 12 }}>
            Это необратимо. Подтверждение действует ещё {deleteLeft} с. Потом в чате с ботом заново выберешь страну и город.
          </div>
          <div className="grid-2">
            <button className="btn ghost" type="button" onClick={() => setDeleteSeconds(0)}>Отмена</button>
            <button className="btn red" type="button" disabled={busy} onClick={async () => { if (await run("/gang/delete/confirm")) setDeleteSeconds(0); }}>Да, удалить</button>
          </div>
        </Sheet>
      )}
    </>
  );
}

function RenameSheet({ data, reload, onClose }: { data: GangData; reload: () => void; onClose: () => void }) {
  const { run, busy } = useAction(reload);
  const [value, setValue] = useState("");
  const left = useCountdown(data.rename_cooldown_seconds ?? 0);
  return (
    <Sheet title="Название банды" onClose={onClose}>
      <div className="gg-hint" style={{ marginTop: 0 }}>
        Сейчас: <b>{data.name}</b>. Смена стоит {fmt(data.rename_price ?? 0)} NHCoin, раз в неделю.
      </div>
      <input className="mass-input" style={{ marginTop: 10 }} value={value} maxLength={64} placeholder="новое название" onChange={(e) => setValue(e.target.value)} />
      <button type="button" className="btn block" style={{ marginTop: 10 }} disabled={busy || left > 0 || value.trim().length < 3}
        onClick={async () => { if (await run("/gang/rename", { name: value.trim() })) onClose(); }}>
        {left > 0 ? `Можно через ${countdown(left)}` : `Сменить за ${fmt(data.rename_price ?? 0)}`}
      </button>
    </Sheet>
  );
}
