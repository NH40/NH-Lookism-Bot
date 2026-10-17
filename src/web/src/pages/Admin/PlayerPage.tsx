// Админка → карточка игрока и действия из неё (по правам роли — `player_rights`).
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { BackHeader, Panel, Screen, fmt } from "../../components/ui";
import { adminSectionPath } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import type { AdminDev, AdminGiveData, AdminMeta, AdminPlayerCard, AdminQuests, AdminStatists, AuditRow, AdminDevLevel, Paged } from "../../types";
import { ConfirmButton, Field, GiveTakeForm, Kv, Pager, Select, Seg, TextInput, useAdminMeta, when } from "./AdminKit";
import "./Admin.css";

type Tab = "give" | "statists" | "dev" | "quests" | "punish" | "log";

export function AdminPlayerPage() {
  const { id = "" } = useParams();
  const uid = Number(id);
  const meta = useAdminMeta();
  const card = useApi<AdminPlayerCard>(`/admin/players/${uid}`);
  return (
    <Screen status={meta.status === "ready" ? card.status : meta.status} error={card.error ?? meta.error}>
      {meta.data && card.data && <PlayerView meta={meta.data} card={card.data} reload={card.reload} />}
    </Screen>
  );
}

function PlayerView({ meta, card, reload }: { meta: AdminMeta; card: AdminPlayerCard; reload: () => Promise<void> }) {
  const r = meta.player_rights;
  const tabs = ([
    r.give && { value: "give", label: "Выдача" },
    r.give && { value: "statists", label: "Статисты" },
    r.dev && { value: "dev", label: "Развитие" },
    r.dev && { value: "quests", label: "Задания" },
    r.punish && { value: "punish", label: "Наказания" },
    r.logs && { value: "log", label: "Журнал" },
  ].filter(Boolean)) as { value: Tab; label: string }[];
  const [tab, setTab] = useState<Tab | null>(tabs[0]?.value ?? null);

  return (
    <div className="page">
      <BackHeader title={card.name} subtitle={`id ${card.id}`} to={adminSectionPath("players")} />
      <PlayerSummary card={card} />
      {tabs.length > 0 && tab && (
        <>
          <Seg value={tab} options={tabs} onChange={setTab} cols={3} />
          {tab === "give" && <GiveTab uid={card.id} meta={meta} onChange={reload} />}
          {tab === "statists" && <StatistsTab uid={card.id} meta={meta} />}
          {tab === "dev" && <DevTab uid={card.id} meta={meta} onChange={reload} />}
          {tab === "quests" && <QuestsTab uid={card.id} />}
          {tab === "punish" && <PunishTab card={card} meta={meta} onChange={reload} />}
          {tab === "log" && <PlayerLogTab uid={card.id} />}
        </>
      )}
    </div>
  );
}

function levels(items: AdminDevLevel[]): string {
  if (!items.length) return "—";
  return items.map((i) => `${i.active ? "★" : i.active2 ? "☆" : ""}${i.name} ${i.level}`).join(", ");
}

function PlayerSummary({ card }: { card: AdminPlayerCard }) {
  const ban = card.banned ? (card.ban_forever ? "навсегда" : `до ${when(card.banned_until)}`) : null;
  const blood = [card.bloodline, card.bloodline2].filter(Boolean).map((b) => `${b!.name} ${b!.level}`).join(" + ") || "—";
  return (
    <>
      <Panel title="Игрок">
        <div style={{ marginBottom: 8 }}>
          {card.username && <span className="adm-code">@{card.username}</span>}
          {card.role_name && <span className="adm-tag gold">{card.role_name}</span>}
          {ban && <span className="adm-tag red">бан {ban}</span>}
        </div>
        {card.banned && card.ban_reason && <div className="adm-hint">Причина: {card.ban_reason}</div>}
        <Kv
          rows={[
            ["Фаза", card.phase_name],
            ["Банда", card.gang ?? "—"],
            ["Город", card.city ?? "—"],
            ["Районы", card.districts],
            ["Клан", card.clan ?? "—"],
            ["Был в игре", when(card.last_active_at)],
            ["Регистрация", when(card.created_at)],
          ]}
        />
      </Panel>
      <Panel title="Ресурсы">
        <Kv rows={card.resources.map((x) => [x.name, x.label] as [string, string])} />
      </Panel>
      <Panel title="Развитие">
        <Kv
          rows={[
            ["Родословная", blood],
            ["Пути", levels(card.paths)],
            ["Техники", levels(card.techniques)],
            ["Гениальности", levels(card.geniuses)],
            ["Пробуждение", card.awakening],
            ["Потенциал", card.potential ?? "—"],
            ["Второе тело", card.second_body ? "да" : "нет"],
            ["Характеристики", Object.values(card.stats).join(" / ")],
            ["Пасс", `${card.bp_level} ур.${card.bp_premium ? " · премиум" : ""}`],
            ["Донат", `${fmt(card.donated_rub)} ₽ · покупок ${card.donate_unlocks}`],
          ]}
        />
      </Panel>
    </>
  );
}

// ---------------------------------------------------------------- выдача

function GiveTab({ uid, meta, onChange }: { uid: number; meta: AdminMeta; onChange: () => Promise<void> }) {
  const data = useApi<AdminGiveData>(`/admin/players/${uid}/give`);
  const reloadAll = async () => {
    await data.reload();
    await onChange();
  };
  const { run, busy } = useAction(reloadAll);
  const [res, setRes] = useState(meta.catalog.resources[0]?.code ?? "coins");
  const [rank, setRank] = useState(meta.catalog.ranks[0]);
  const [stars, setStars] = useState(0);
  const [cardQuery, setCardQuery] = useState("");
  const [cardCode, setCardCode] = useState<string | null>(null);
  const give = (body: Record<string, unknown>) => run(`/admin/players/${uid}/give`, body);
  const d = data.data;
  const cards = d ? d.cards.filter((c) => !cardQuery || c.name.toLowerCase().includes(cardQuery.toLowerCase()) || c.code.includes(cardQuery.toLowerCase())).slice(0, 8) : [];
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <div className="adm-split">
          <Panel title="Ресурсы">
            <Field label="Ресурс">
              <Select
                value={res}
                onChange={setRes}
                options={d.resources.map((x) => ({ value: x.code, label: `${x.name} — ${x.label}` }))}
              />
            </Field>
            <GiveTakeForm busy={busy} onSubmit={(delta) => give({ kind: "resource", code: res, delta })} />
          </Panel>
          <Panel title="Статисты вручную">
            <div className="adm-hint">Любой ранг и звёзды. Быстрые кнопки — во вкладке «Статисты».</div>
            <div className="grid-2" style={{ gap: 8 }}>
              <Field label="Ранг">
                <Select value={rank} onChange={setRank} options={meta.catalog.ranks.map((x) => ({ value: x, label: x }))} />
              </Field>
              <Field label="Звёзды">
                <Select value={stars} onChange={setStars} options={[0, 1, 2, 3, 4, 5].map((x) => ({ value: x, label: `${x}★` }))} />
              </Field>
            </div>
            <GiveTakeForm busy={busy} onSubmit={(delta) => give({ kind: "statist", rank, stars, delta })} />
          </Panel>
          <Panel title="Уникальная карта">
            <Field label="Поиск карты">
              <TextInput value={cardQuery} onChange={(v) => { setCardQuery(v); setCardCode(null); }} placeholder="Имя или код" />
            </Field>
            {!cardCode && cardQuery && (
              <div className="adm-list" style={{ marginBottom: 10 }}>
                {cards.map((c) => (
                  <button key={c.code} type="button" className="adm-item" onClick={() => { setCardCode(c.code); setCardQuery(c.name); }}>
                    <b>{c.name}</b>
                    <span className="adm-code">{c.code}</span>
                  </button>
                ))}
                {!cards.length && <div className="adm-hint">Ничего не нашлось.</div>}
              </div>
            )}
            {cardCode && <GiveTakeForm busy={busy} onSubmit={(delta) => give({ kind: "card", code: cardCode, delta })} />}
          </Panel>
          <Panel title={`Свитки пропуска · ${fmt(d.scrolls)}`}>
            <GiveTakeForm busy={busy} onSubmit={(delta) => give({ kind: "scrolls", delta })} />
          </Panel>
          <Panel title={`Опыт пасса · ${fmt(d.bp_xp)}`}>
            <GiveTakeForm busy={busy} onSubmit={(delta) => give({ kind: "xp", delta })} />
          </Panel>
        </div>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- статисты

function StatistsTab({ uid, meta }: { uid: number; meta: AdminMeta }) {
  const data = useApi<AdminStatists>(`/admin/players/${uid}/statists`);
  const { run, busy } = useAction(data.reload);
  const [open, setOpen] = useState<string | null>(null);
  const [rank, setRank] = useState(meta.catalog.ranks[0]);
  const post = (body: Record<string, unknown>) => run(`/admin/players/${uid}/statists`, body);
  const d = data.data;
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <div className="adm-split">
          <Panel title="Армия">
            <Kv rows={[["Всего статистов", fmt(d.total)], ["В атаке", fmt(d.attack)], ["В защите", fmt(d.defense)]]} />
          </Panel>
          <Panel title="Новый отряд (0★)">
            <Field label="Ранг">
              <Select value={rank} onChange={setRank} options={meta.catalog.ranks.map((x) => ({ value: x, label: x }))} />
            </Field>
            <div className="grid-3" style={{ gap: 6 }}>
              {meta.catalog.statist_give_amounts.map((n) => (
                <button key={n} type="button" className="btn green small" disabled={busy} onClick={() => post({ action: "give", rank, amount: n })}>
                  +{fmt(n)}
                </button>
              ))}
            </div>
          </Panel>
          <Panel title={`Отряды · ${d.squads.length}`}>
            <div className="adm-list">
              {d.squads.map((s) => (
                <div key={s.key}>
                  <button type="button" className={`adm-item ${open === s.key ? "on" : ""}`} onClick={() => setOpen(open === s.key ? null : s.key)}>
                    <div>
                      <b>{s.title}</b>
                      <small>атака {fmt(s.attack)} · защита {fmt(s.defense)}</small>
                    </div>
                    <div className="adm-right">{fmt(s.total)}</div>
                  </button>
                  {open === s.key && (
                    <div style={{ display: "grid", gap: 6, margin: "6px 0 4px" }}>
                      <div className="grid-3" style={{ gap: 6 }}>
                        {meta.catalog.statist_take_percents.map((p) => (
                          <button key={p} type="button" className="btn ghost small" disabled={busy} onClick={() => post({ action: "take", key: s.key, percent: p })}>
                            −{p === 100 ? "все" : `${p}%`}
                          </button>
                        ))}
                      </div>
                      <div className="grid-3" style={{ gap: 6 }}>
                        {meta.catalog.statist_add_amounts.map((n) => (
                          <button key={n} type="button" className="btn green small" disabled={busy} onClick={() => post({ action: "add", key: s.key, amount: n })}>
                            +{fmt(n)}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {!d.squads.length && <div className="adm-hint">Статистов нет.</div>}
            </div>
            {d.squads.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <ConfirmButton disabled={busy} onConfirm={() => post({ action: "wipe" })}>
                  Забрать всех статистов
                </ConfirmButton>
              </div>
            )}
          </Panel>
        </div>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- развитие

function DevTab({ uid, meta, onChange }: { uid: number; meta: AdminMeta; onChange: () => Promise<void> }) {
  const data = useApi<AdminDev>(`/admin/players/${uid}/dev`);
  const reloadAll = async () => {
    await data.reload();
    await onChange();
  };
  const { run, busy } = useAction(reloadAll);
  const c = meta.catalog;
  const [kind, setKind] = useState(c.dev_kinds[0]?.kind ?? "path");
  const [item, setItem] = useState<string>(c.dev_kinds[0]?.items[0]?.code ?? "");
  const [level, setLevel] = useState(1);
  const [slot, setSlot] = useState(1);
  const [blood, setBlood] = useState<string>(c.bloodlines[0]?.code ?? "");
  const [bloodLevel, setBloodLevel] = useState(1);
  const [stat, setStat] = useState(c.stats[0]?.code ?? "strength");
  const [rank, setRank] = useState(c.ranks[0]);
  const dev = (body: Record<string, unknown>) => run(`/admin/players/${uid}/dev`, body);
  const d = data.data;
  const kindDef = c.dev_kinds.find((k) => k.kind === kind);
  const sys = d?.systems[kind];
  const levelOptions = Array.from({ length: c.max_level + 1 }, (_, i) => ({ value: i, label: i === 0 ? "0 — забрать" : `${i}` }));
  return (
    <Screen status={data.status} error={data.error}>
      {d && kindDef && (
        <div className="adm-split">
          <Panel title="Фаза">
            <div className="grid-3" style={{ gap: 6 }}>
              {c.phases.map((p) => (
                <button key={p.code} type="button" className={`btn small ${d.phase === p.code ? "" : "ghost"}`} disabled={busy || d.phase === p.code}
                  onClick={() => dev({ action: "phase", value: p.code })}>
                  {p.name}
                </button>
              ))}
            </div>
          </Panel>
          <Panel title="Пути, техники, гениальности">
            <Seg value={kind} onChange={(k) => { setKind(k); setItem(c.dev_kinds.find((x) => x.kind === k)?.items[0]?.code ?? ""); }}
              options={c.dev_kinds.map((k) => ({ value: k.kind, label: k.title }))} cols={3} />
            <div className="adm-list" style={{ marginBottom: 10 }}>
              {kindDef.items.filter((i) => sys && i.code in sys.owned).map((i) => (
                <div key={i.code} className={`adm-item ${sys?.active === i.code ? "on" : ""}`}>
                  <b>{sys?.active === i.code ? "★ " : ""}{i.name}</b>
                  <span className="adm-right">ур. {sys!.owned[i.code]}</span>
                </div>
              ))}
              {sys && !Object.keys(sys.owned).length && <div className="adm-hint">Ничего не изучено.</div>}
            </div>
            <Field label="Пункт">
              <Select value={item} onChange={setItem} options={kindDef.items.map((i) => ({ value: i.code, label: `${i.name}${sys && i.code in sys.owned ? ` · ур. ${sys.owned[i.code]}` : ""}` }))} />
            </Field>
            <div className="adm-inline">
              <Select value={level} onChange={setLevel} options={levelOptions} />
              <button type="button" className="btn small" disabled={busy || !item} onClick={() => dev({ action: "level", kind, code: item, level })}>Уровень</button>
              <button type="button" className="btn ghost small" disabled={busy || !item || !(sys && item in sys.owned)} onClick={() => dev({ action: "active", kind, code: item })}>Активный</button>
            </div>
          </Panel>
          <Panel title="Родословные">
            <Seg value={String(slot)} onChange={(v) => setSlot(Number(v))} options={[{ value: "1", label: "Слот 1" }, { value: "2", label: "Слот 2" }]} />
            <div className="adm-hint">
              Сейчас: {d.bloodlines[String(slot)]?.code ? `${c.bloodlines.find((b) => b.code === d.bloodlines[String(slot)].code)?.name ?? d.bloodlines[String(slot)].code} ${d.bloodlines[String(slot)].level}` : "—"}
            </div>
            <div className="adm-inline" style={{ marginBottom: 8 }}>
              <Select value={blood} onChange={setBlood} options={c.bloodlines.map((b) => ({ value: b.code, label: b.name }))} />
              <button type="button" className="btn small" disabled={busy} onClick={() => dev({ action: "bloodline", slot, code: blood })}>Выдать</button>
              <button type="button" className="btn ghost small" disabled={busy || !d.bloodlines[String(slot)]?.code} onClick={() => dev({ action: "bloodline", slot, code: null })}>Снять</button>
            </div>
            <div className="adm-inline">
              <Select value={bloodLevel} onChange={setBloodLevel} options={levelOptions.slice(1)} />
              <button type="button" className="btn small" disabled={busy || !d.bloodlines[String(slot)]?.code} onClick={() => dev({ action: "blood_level", slot, level: bloodLevel })}>Уровень</button>
            </div>
          </Panel>
          <Panel title="Прочее">
            <div className="grid-2" style={{ gap: 6, marginBottom: 10 }}>
              <button type="button" className={`btn small ${d.second_body ? "violet" : "ghost"}`} disabled={busy} onClick={() => dev({ action: "body" })}>
                Второе тело: {d.second_body ? "вкл" : "выкл"}
              </button>
              <button type="button" className={`btn small ${d.premium ? "gold" : "ghost"}`} disabled={busy} onClick={() => dev({ action: "pass" })}>
                Премиум-пасс: {d.premium ? "вкл" : "выкл"}
              </button>
            </div>
            <Field label={`Пробуждение · сейчас ${d.awakening}`}>
              <div className="adm-grid-btn">
                {Array.from({ length: c.awakening_max + 1 }, (_, i) => (
                  <button key={i} type="button" className={`btn small ${d.awakening === i ? "" : "ghost"}`} disabled={busy} onClick={() => dev({ action: "awakening", level: i })}>{i}</button>
                ))}
              </div>
            </Field>
            <Field label={`Потенциал · сейчас ${d.potential ?? "—"}`}>
              <div className="grid-3" style={{ gap: 6 }}>
                {c.potentials.map((p) => (
                  <button key={p} type="button" className={`btn small ${d.potential === p ? "" : "ghost"}`} disabled={busy} onClick={() => dev({ action: "potential", value: p })}>{p}</button>
                ))}
              </div>
            </Field>
          </Panel>
          <Panel title="Характеристики">
            <Kv rows={c.stats.map((s) => [s.name, d.stats[s.code]] as [string, string])} />
            <div className="adm-inline" style={{ marginTop: 10 }}>
              <Select value={stat} onChange={setStat} options={c.stats.map((s) => ({ value: s.code, label: s.name }))} />
              <Select value={rank} onChange={setRank} options={c.ranks.map((r) => ({ value: r, label: r }))} />
              <button type="button" className="btn small" disabled={busy} onClick={() => dev({ action: "stat", code: stat, value: rank })}>Ранг</button>
            </div>
          </Panel>
        </div>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- задания

function QuestsTab({ uid }: { uid: number }) {
  const data = useApi<AdminQuests>(`/admin/players/${uid}/quests`);
  const { run, busy } = useAction(data.reload);
  const d = data.data;
  const post = (body: Record<string, unknown>) => run(`/admin/players/${uid}/quests`, body);
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <div className="adm-split">
          <Panel title="Ежедневные">
            <div className="adm-list">
              {d.daily.map((q) => (
                <div key={q.slot} className="adm-item">
                  <div>
                    <b>{q.title}</b>
                    <small>{fmt(q.progress)} / {fmt(q.target)}</small>
                  </div>
                  <button type="button" className="btn small" disabled={busy} onClick={() => post({ slot: q.slot })}>Засчитать</button>
                </div>
              ))}
              {!d.daily.length && <div className="adm-hint">Открытых нет.</div>}
            </div>
          </Panel>
          <Panel title="Квесты развития">
            <div className="adm-list">
              {d.dev.map((q) => (
                <div key={q.id} className="adm-item">
                  <b>{q.title}</b>
                  <button type="button" className="btn small" disabled={busy} onClick={() => post({ dev_id: q.id })}>Засчитать</button>
                </div>
              ))}
              {!d.dev.length && <div className="adm-hint">Открытых нет.</div>}
            </div>
          </Panel>
          {(d.daily.length > 0 || d.dev.length > 0) && (
            <button type="button" className="btn green block" disabled={busy} onClick={() => post({})}>Засчитать все</button>
          )}
        </div>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- наказания

function PunishTab({ card, meta, onChange }: { card: AdminPlayerCard; meta: AdminMeta; onChange: () => Promise<void> }) {
  const { run, busy } = useAction(onChange);
  const navigate = useNavigate();
  const [duration, setDuration] = useState(meta.catalog.ban_durations[0]?.code ?? "1h");
  const [reason, setReason] = useState("");
  const punish = (body: Record<string, unknown>) => run(`/admin/players/${card.id}/punish`, body);
  return (
    <div className="adm-split">
      <Panel title="Бан" tone={card.banned ? "red" : "blue"}>
        {card.banned ? (
          <button type="button" className="btn green block" disabled={busy} onClick={() => punish({ action: "unban" })}>Снять бан</button>
        ) : (
          <>
            <Seg value={duration} onChange={setDuration} options={meta.catalog.ban_durations.map((x) => ({ value: x.code, label: x.name }))} cols={3} />
            <Field label={`Причина (необязательно, до ${meta.catalog.ban_reason_max})`}>
              <TextInput value={reason} onChange={setReason} placeholder="Игрок увидит её в сообщении" />
            </Field>
            <ConfirmButton disabled={busy} onConfirm={() => punish({ action: "ban", duration, reason })}>Забанить</ConfirmButton>
          </>
        )}
      </Panel>
      <Panel title="Сброс">
        <div className="adm-split">
          <button type="button" className="btn ghost block" disabled={busy} onClick={() => punish({ action: "cooldowns" })}>Сбросить кулдауны и щиты</button>
          <div className="adm-hint">Сброс прогресса — как удаление банды игроком: донат и покупки чёрного рынка сохраняются.</div>
          <ConfirmButton disabled={busy} onConfirm={() => punish({ action: "reset" })}>Сбросить прогресс</ConfirmButton>
        </div>
      </Panel>
      <Panel title="Удаление" tone="red">
        <div className="adm-hint">Игрок стирается полностью. Владелец клана с участниками — сначала передайте клан.</div>
        <ConfirmButton disabled={busy} onConfirm={async () => {
          const r = await run(`/admin/players/${card.id}/punish`, { action: "delete" });
          if (r?.deleted) navigate(adminSectionPath("players"));
        }}>Удалить аккаунт</ConfirmButton>
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------- журнал игрока

type PlayerLogKind = "audit" | "activity" | "payments";

function PlayerLogTab({ uid }: { uid: number }) {
  const [kind, setKind] = useState<PlayerLogKind>("audit");
  return (
    <Panel title="Журнал">
      <Seg value={kind} onChange={setKind} options={[{ value: "audit", label: "Админы" }, { value: "activity", label: "Действия" }, { value: "payments", label: "Платежи" }]} cols={3} />
      <PlayerLogList key={kind} uid={uid} kind={kind} />
    </Panel>
  );
}

function PlayerLogList({ uid, kind }: { uid: number; kind: PlayerLogKind }) {
  const [page, setPage] = useState(0);
  const path = kind === "audit" ? `/admin/logs/audit?target_id=${uid}&page=${page}` : `/admin/logs/${kind}?target_id=${uid}&page=${page}`;
  const data = useApi<Paged<Record<string, unknown>>>(path);
  return (
    <>
      <Screen status={data.status} error={data.error}>
        {data.data && (
          <>
            <div className="adm-list">
              {data.data.rows.map((row, i) => <LogRow key={i} kind={kind} row={row} />)}
              {!data.data.rows.length && <div className="adm-hint">Записей нет.</div>}
            </div>
            <Pager page={page} total={data.data.total} perPage={data.data.per_page} onPage={setPage} />
          </>
        )}
      </Screen>
    </>
  );
}

export function LogRow({ kind, row }: { kind: string; row: Record<string, unknown> }) {
  if (kind === "audit") {
    const r = row as unknown as AuditRow;
    const details = Object.keys(r.details ?? {}).length ? JSON.stringify(r.details) : "";
    return (
      <div className="adm-item">
        <div style={{ minWidth: 0 }}>
          <b>{r.action}</b>
          <small>админ {r.admin_id}{r.target_id ? ` → ${r.target_id}` : ""}</small>
          {details && <small style={{ wordBreak: "break-all" }}>{details}</small>}
        </div>
        <div className="adm-right">{when(r.created_at)}</div>
      </div>
    );
  }
  if (kind === "activity") {
    return (
      <div className="adm-item">
        <div style={{ minWidth: 0 }}>
          <b>{String(row.text)}</b>
          <small>{String(row.kind)}</small>
        </div>
        <div className="adm-right">{when(row.created_at as string)}</div>
      </div>
    );
  }
  if (kind === "payments") {
    return (
      <div className="adm-item">
        <div>
          <b>{fmt(Number(row.rub))} ₽ → {fmt(Number(row.coins ?? 0))} 💎</b>
          <small>{row.username ? `@${row.username}` : `id ${row.user_id}`}</small>
        </div>
        <div className="adm-right">{when(row.created_at as string)}</div>
      </div>
    );
  }
  if (kind === "clan") {
    return (
      <div className="adm-item">
        <div>
          <b>{String(row.clan)} · {fmt(Number(row.price))} 💎</b>
          <small>{row.username ? `@${row.username}` : `id ${row.user_id}`}</small>
        </div>
        <div className="adm-right">{when(row.created_at as string)}</div>
      </div>
    );
  }
  return (
    <div className="adm-item">
      <div>
        <b>{String(row.kind)} · <span className="adm-code">{String(row.code)}</span></b>
        <small>покупателей {String(row.buyers)} · макс. ур. {String(row.max_level)}</small>
      </div>
    </div>
  );
}
