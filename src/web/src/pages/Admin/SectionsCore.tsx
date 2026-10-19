// Админка — разделы ядра: бета/техрежим, роли, настройки на лету, патч/вайп, статистика, журналы.
import { useState } from "react";
import { Link } from "react-router-dom";
import { Chip, Panel, Screen, countdown, fmt } from "../../components/ui";
import { adminPlayerPath } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import type { AdminConfigKey, AdminMeta, AdminSystem, Paged } from "../../types";
import { ConfirmButton, Field, Kv, Pager, Select, Seg, TextInput } from "./AdminKit";
import { BarChart, type Point } from "./Charts";
import { LogRow } from "./PlayerPage";

// ---------------------------------------------------------------- бета и техрежим

export function SystemSection() {
  const data = useApi<AdminSystem>("/admin/system");
  const { run, busy } = useAction(data.reload);
  const [code, setCode] = useState("");
  const d = data.data;
  const beta = (action: string, withCode = true) => run("/admin/system/beta", { action, code: withCode && code.trim() ? code.trim() : null });
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <div className="adm-split">
          <Panel title="Бета-режим" tone={d.beta ? "gold" : "blue"}>
            {d.beta ? (
              <>
                <Kv rows={[["Код", <span className="adm-code">{d.beta.code}</span>], ["Допущено игроков", fmt(d.beta.allowed)]]} />
                <div className="adm-hint" style={{ marginTop: 10 }}>Смена кода не сбрасывает уже допущенных.</div>
                <div className="adm-inline" style={{ marginBottom: 10 }}>
                  <TextInput value={code} onChange={setCode} placeholder="Новый код (пусто — сгенерировать)" />
                  <button type="button" className="btn small" disabled={busy} onClick={async () => { await beta("change"); setCode(""); }}>Сменить</button>
                </div>
                <ConfirmButton disabled={busy} onConfirm={() => beta("disable", false)}>Выключить бету (допуски сбросятся)</ConfirmButton>
              </>
            ) : (
              <>
                <div className="adm-hint">Пока бета включена, все кроме админов вводят кодовое слово перед любым действием в боте.</div>
                <div className="adm-inline">
                  <TextInput value={code} onChange={setCode} placeholder="Код (пусто — сгенерировать)" />
                  <button type="button" className="btn gold small" disabled={busy} onClick={async () => { await beta("enable"); setCode(""); }}>Включить</button>
                </div>
              </>
            )}
          </Panel>
          <Panel title="Техрежим" tone={d.tech ? "red" : "blue"}>
            <div className="adm-hint">Бот отвечает только админам — для перерывов на обслуживание.</div>
            <ConfirmButton tone={d.tech ? "green" : "ghost"} disabled={busy} onConfirm={() => run("/admin/system/tech")}>
              {d.tech ? "Выключить техрежим" : "Включить техрежим"}
            </ConfirmButton>
          </Panel>
        </div>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- роли

interface RolesData {
  supers: number[];
  staff: { id: number; username: string | null; role: string; role_name: string }[];
}

export function RolesSection({ meta }: { meta: AdminMeta }) {
  const data = useApi<RolesData>("/admin/roles");
  const { run, busy } = useAction(data.reload);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState(meta.catalog.roles[0]?.code ?? "support");
  const d = data.data;
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <div className="adm-split">
          <Panel title="Выдать роль">
            <Field label="Игрок">
              <TextInput value={query} onChange={setQuery} placeholder="@nick или id" />
            </Field>
            <Seg value={role} onChange={setRole} options={meta.catalog.roles.map((r) => ({ value: r.code, label: r.name }))} cols={3} />
            <button type="button" className="btn block" disabled={busy || !query.trim()} onClick={async () => { if (await run("/admin/roles/set", { query: query.trim(), role })) setQuery(""); }}>
              Выдать
            </button>
          </Panel>
          <Panel title="Сотрудники">
            <div className="adm-list">
              {d.supers.map((id) => (
                <div key={id} className="adm-item">
                  <div><b>id {id}</b><small>Супер-админ (из .env)</small></div>
                </div>
              ))}
              {d.staff.map((s) => (
                <div key={s.id} className="adm-item">
                  <Link to={adminPlayerPath(s.id)} style={{ color: "inherit", textDecoration: "none", minWidth: 0 }}>
                    <b>{s.username ? `@${s.username}` : `id ${s.id}`}</b>
                    <small>{s.role_name}</small>
                  </Link>
                  <ConfirmButton small tone="ghost" disabled={busy} onConfirm={() => run("/admin/roles/remove", { user_id: s.id })}>Снять</ConfirmButton>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- настройки на лету

export function ConfigSection({ meta }: { meta: AdminMeta }) {
  const data = useApi<{ keys: AdminConfigKey[] }>("/admin/config");
  const { run, busy } = useAction(data.reload);
  const [open, setOpen] = useState<string | null>(null);
  const [value, setValue] = useState("");
  const [hours, setHours] = useState(0);
  return (
    <Screen status={data.status} error={data.error}>
      {data.data && (
        <Panel title="Настройки на лету">
          <div className="adm-hint">Действуют без перезапуска; в другом процессе (бот / Mini App) — через ~15 с.</div>
          <div className="adm-list">
            {data.data.keys.map((k) => (
              <div key={k.key}>
                <button type="button" className={`adm-item ${open === k.key ? "on" : ""}`} onClick={() => { setOpen(open === k.key ? null : k.key); setValue(String(k.value)); setHours(0); }}>
                  <div>
                    <b>{k.title}</b>
                    <small>
                      по умолчанию {k.default} · {k.min}…{k.max}
                      {k.overridden ? (k.left_seconds != null ? ` · изменено, ещё ${countdown(k.left_seconds)}` : " · изменено навсегда") : ""}
                    </small>
                  </div>
                  <div className="adm-right">
                    {k.value}
                    {k.overridden && <span className="adm-tag gold">★</span>}
                  </div>
                </button>
                {open === k.key && (
                  <div style={{ display: "grid", gap: 8, margin: "8px 0" }}>
                    <TextInput type="number" value={value} onChange={setValue} placeholder={`${k.min}…${k.max}`} />
                    {k.expiring && (
                      <Select value={hours} onChange={setHours} options={meta.catalog.config_durations.map((x) => ({ value: x.hours, label: x.name }))} />
                    )}
                    <div className="grid-2" style={{ gap: 6 }}>
                      <button type="button" className="btn small" disabled={busy || !value.trim()} onClick={() => run("/admin/config/set", { key: k.key, value, hours })}>Сохранить</button>
                      <button type="button" className="btn ghost small" disabled={busy || !k.overridden} onClick={() => run("/admin/config/reset", { key: k.key })}>По умолчанию</button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Panel>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- патч и вайп

export function PatchSection() {
  const data = useApi<{ start_coins: number; start_tickets: number; running: boolean }>("/admin/patch");
  const { run, busy } = useAction(data.reload);
  const [armed, setArmed] = useState<string | null>(null);
  const arm = async (kind: string) => {
    if (await run("/admin/patch/arm", { kind })) {
      setArmed(kind);
      window.setTimeout(() => setArmed((k) => (k === kind ? null : k)), 30000);
    }
  };
  const confirm = async (kind: string) => {
    setArmed(null);
    await run("/admin/patch/confirm", { kind });
  };
  const d = data.data;
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <div className="adm-split">
          <Panel title="Патч (конец сезона)" tone="gold">
            <div className="adm-hint">
              Сброс прогресса ВСЕХ игроков с сохранением доната. Награды топа сезона начисляются после сброса. Старт:{" "}
              {fmt(d.start_coins)} NHCoin, {fmt(d.start_tickets)} тикетов. Подтверждение — два шага за 30 секунд.
            </div>
            {d.running ? (
              <div className="adm-hint">Патч уже выполняется — отчёт придёт в чат с ботом.</div>
            ) : armed === "patch" ? (
              <button type="button" className="btn red block" disabled={busy} onClick={() => confirm("patch")}>Да, запустить патч</button>
            ) : (
              <button type="button" className="btn gold block" disabled={busy} onClick={() => arm("patch")}>Запустить патч…</button>
            )}
          </Panel>
          <Panel title="Вайп базы" tone="red">
            <div className="adm-hint">Стирает ВСЕ игровые данные (кроме переноса доната 1.3). Необратимо.</div>
            {armed === "wipe" ? (
              <button type="button" className="btn red block" disabled={busy} onClick={() => confirm("wipe")}>Да, стереть всё</button>
            ) : (
              <button type="button" className="btn ghost block adm-danger" disabled={busy} onClick={() => arm("wipe")}>Вайп…</button>
            )}
          </Panel>
        </div>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- статистика

type StatTab = "charts" | "overview" | "donate" | "economy" | "server";

function mb(bytes: number): string {
  return bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} ГБ` : `${Math.round(bytes / 1e6)} МБ`;
}

export function StatsSection() {
  const [tab, setTab] = useState<StatTab>("charts");
  return (
    <>
      <Seg value={tab} onChange={setTab} cols={3} options={[
        { value: "charts", label: "Графики" }, { value: "overview", label: "Игроки" }, { value: "donate", label: "Донат" },
        { value: "economy", label: "Экономика" }, { value: "server", label: "Сервер" },
      ]} />
      {/* key — свой экземпляр на вкладку: иначе на миг рисуются данные прошлой вкладки */}
      {tab === "charts" ? <ChartsTab /> : <StatsTab key={tab} tab={tab} />}
    </>
  );
}

interface Series {
  registrations: Point[];
  donate: Point[];
  active: Point[];
  active_days: number;
}

function ChartsTab() {
  const [days, setDays] = useState<"7" | "30" | "90">("30");
  const series = useApi<Series>(`/admin/stats/series?days=${days}`);
  const overview = useApi<Record<string, number>>("/admin/stats/overview");
  const o = overview.data;
  const s = series.data;
  const last = (xs: Point[] | undefined) => (xs && xs.length ? xs[xs.length - 1].value : 0);
  return (
    <div className="adm-split">
      {o && (
        <div className="grid-2" style={{ gap: 8 }}>
          <Chip value={fmt(Number(o.total ?? 0))} label="игроков всего" />
          <Chip value={fmt(Number(o.online_24h ?? 0))} label="активны за 24 ч" variant="active" />
          <Chip value={fmt(last(s?.registrations))} label="новых сегодня" />
          <Chip value={`${fmt(last(s?.donate))} ₽`} label="донат сегодня" variant="gold" />
        </div>
      )}
      <Seg value={days} onChange={setDays} options={[{ value: "7", label: "7 дней" }, { value: "30", label: "30 дней" }, { value: "90", label: "90 дней" }]} cols={3} />
      <Screen status={series.status} error={series.error}>
        {s && (
          <>
            <Panel title="Регистрации">
              <BarChart data={s.registrations} color="var(--cyan)" />
            </Panel>
            <Panel title={`Активные игроки · ${s.active_days} дн.`} tone="green">
              <BarChart data={s.active} color="var(--green)" />
              <div className="adm-hint" style={{ marginTop: 6, marginBottom: 0 }}>Журнал действий хранится {s.active_days} дней — поэтому период короче.</div>
            </Panel>
            <Panel title="Донат, ₽" tone="gold">
              <BarChart data={s.donate} color="var(--gold)" unit=" ₽" />
            </Panel>
          </>
        )}
      </Screen>
    </div>
  );
}

function StatsTab({ tab }: { tab: StatTab }) {
  const data = useApi<Record<string, any>>(`/admin/stats/${tab}`);
  const d = data.data;
  const n = (x: unknown) => fmt(Number(x ?? 0));
  return (
    <>
      <Screen status={data.status} error={data.error}>
        {d && tab === "overview" && (
          <Panel title="Игроки">
            <Kv rows={[
              ["Всего", n(d.total)], ["Банд", n(d.gangs)], ["Новых сегодня", n(d.reg_today)], ["Новых за 7 дней", n(d.reg_7d)],
              ["Активны 24 ч", n(d.online_24h)], ["Активны 7 дней", n(d.online_7d)], ["В бане", n(d.banned)],
              ["Удержание D1", d.d1_cohort ? `${Math.round((100 * d.d1_kept) / d.d1_cohort)}% (${d.d1_kept}/${d.d1_cohort})` : "—"],
              ["Удержание D7", d.d7_cohort ? `${Math.round((100 * d.d7_kept) / d.d7_cohort)}% (${d.d7_kept}/${d.d7_cohort})` : "—"],
            ]} />
          </Panel>
        )}
        {d && tab === "donate" && (
          <div className="adm-split">
            <Panel title="Донат" tone="gold">
              <Kv rows={[
                ["Всего", `${n(d.total)} ₽`], ["Сегодня", `${n(d.today)} ₽`], ["7 дней", `${n(d.d7)} ₽`], ["30 дней", `${n(d.d30)} ₽`],
                ["Донатеров", n(d.donors)], ["Покупок чёрного рынка", n(d.unlocks)], ["Клановых покупок", n(d.clan_purchases)],
                ["Донат-коинов на руках", n(d.circulation)], ["Премиум-пасс сезона", n(d.bp_premium)],
              ]} />
            </Panel>
            <Panel title="Топ донатеров">
              <div className="adm-list">
                {(d.top as { user_id: number; username: string | null; total: number }[]).map((t) => (
                  <Link key={t.user_id} to={adminPlayerPath(t.user_id)} className="adm-item">
                    <b>{t.username ? `@${t.username}` : `id ${t.user_id}`}</b>
                    <span className="adm-right">{n(t.total)} ₽</span>
                  </Link>
                ))}
              </div>
            </Panel>
          </div>
        )}
        {d && tab === "economy" && (
          <div className="adm-split">
            <Panel title="Ресурсы у игроков">
              <Kv rows={[
                ["NHCoin", n(d.res.coins)], ["Тикеты", n(d.res.tickets)], ["Очки развития", n(d.res.dev_pts)], ["Очки пути", n(d.res.path_pts)],
                ["Фрагменты пути", n(d.res.path_fr)], ["Фрагменты техник", n(d.res.tech_fr)], ["Фрагменты гениальности", n(d.res.gen_fr)],
                ["Капли крови", n(d.res.blood)], ["Донат-коины", n(d.res.donate)], ["Статистов", n(d.extras)],
              ]} />
            </Panel>
            <Panel title="Мир">
              <Kv rows={[
                ["Районов у игроков", n(d.owned)], ["Районов у ботов", n(d.bots)], ["Кланов", n(d.clans)], ["Средний уровень пасса", Number(d.bp_avg ?? 0).toFixed(1)],
                ...((d.biz as { type: string; count: number }[]).map((b) => [`Бизнес: ${b.type}`, n(b.count)] as [string, string])),
              ]} />
            </Panel>
          </div>
        )}
        {d && tab === "server" && (
          <Panel title="Сервер">
            <Kv rows={[
              ["CPU", d.srv?.available ? `${d.srv.cpu ?? "—"}%` : "нет psutil"],
              ["RAM", d.srv?.available ? `${mb(d.srv.ram_used)} / ${mb(d.srv.ram_total)}` : "—"],
              ["Диск", d.srv?.available ? `${mb(d.srv.disk_used)} / ${mb(d.srv.disk_total)}` : "—"],
              ["База данных", mb(d.db_size)], ["Redis", d.redis_mem ?? "—"], ["Аптайм API", countdown(d.uptime)],
            ]} />
          </Panel>
        )}
      </Screen>
    </>
  );
}

// ---------------------------------------------------------------- журналы

type LogKind = "audit" | "payments" | "clan" | "blackmarket";

export function LogsSection() {
  const [kind, setKind] = useState<LogKind>("audit");
  return (
    <>
      <Seg value={kind} onChange={setKind} options={[
        { value: "audit", label: "Админы" }, { value: "payments", label: "Платежи" },
        { value: "clan", label: "Клан. донат" }, { value: "blackmarket", label: "Чёрный рынок" },
      ]} />
      <LogsList key={kind} kind={kind} />
    </>
  );
}

function LogsList({ kind }: { kind: LogKind }) {
  const [page, setPage] = useState(0);
  const [adminId, setAdminId] = useState<number | 0>(0);
  const path = kind === "audit" ? `/admin/logs/audit?page=${page}${adminId ? `&admin_id=${adminId}` : ""}` : `/admin/logs/${kind}?page=${page}`;
  const data = useApi<Paged<Record<string, unknown>> & { staff?: { id: number; username: string | null }[] }>(path);
  return (
    <>
      <Panel>
        <Screen status={data.status} error={data.error}>
          {data.data && (
            <>
              {kind === "audit" && data.data.staff && (
                <Field label="Админ">
                  <Select value={adminId} onChange={(v) => { setAdminId(v); setPage(0); }}
                    options={[{ value: 0, label: "Все" }, ...data.data.staff.map((s) => ({ value: s.id, label: s.username ? `@${s.username}` : `id ${s.id}` }))]} />
                </Field>
              )}
              <div className="adm-list">
                {data.data.rows.map((row, i) => <LogRow key={i} kind={kind} row={row} />)}
                {!data.data.rows.length && <div className="adm-hint">Записей нет.</div>}
              </div>
              {kind !== "blackmarket" && <Pager page={page} total={data.data.total} perPage={data.data.per_page} onPage={setPage} />}
            </>
          )}
        </Screen>
      </Panel>
    </>
  );
}
