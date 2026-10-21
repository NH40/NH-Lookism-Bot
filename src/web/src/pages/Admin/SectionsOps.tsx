// Админка — разделы мира и контента: рассылка, промокоды, рефералы, события, мир, кланы, сезон.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../../api";
import { Panel, Screen, countdown, fmt, useToast } from "../../components/ui";
import { adminPlayerPath } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import type { AdminCity, AdminClan, AdminEvent, AdminMeta, AdminPromo, AdminReferral, AdminSeason, AdminSeasonPlayer } from "../../types";
import { ConfirmButton, Field, GiveTakeForm, Kv, Select, Seg, TextInput, parseSigned, when } from "./AdminKit";

/** Поиск: поле + кнопка, результат — в колбэк (ошибка — тост). */
function SearchBox({ placeholder, onSearch, busy }: { placeholder: string; onSearch: (q: string) => void; busy?: boolean }) {
  const [q, setQ] = useState("");
  return (
    <form className="adm-inline" onSubmit={(e) => { e.preventDefault(); if (q.trim()) onSearch(q.trim()); }}>
      <TextInput value={q} onChange={setQ} placeholder={placeholder} />
      <button type="submit" className="btn small" disabled={busy || !q.trim()}>Найти</button>
    </form>
  );
}

// ---------------------------------------------------------------- рассылка и массовая выдача

export function MassSection({ meta }: { meta: AdminMeta }) {
  const c = meta.catalog;
  const [mode, setMode] = useState<"broadcast" | "grant">("broadcast");
  const [filter, setFilter] = useState(c.mass_filters[0]?.code ?? "all");
  const [clan, setClan] = useState("");
  const [count, setCount] = useState<{ count: number; audience: string } | null>(null);
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState("");
  const [button, setButton] = useState("");
  const [resource, setResource] = useState(c.resources[0]?.code ?? "coins");
  const [amount, setAmount] = useState("");
  const { run, busy } = useAction();
  const toast = useToast();
  const audience = { filter, clan: filter === "clan" ? clan : null };

  useEffect(() => {
    setCount(null);
    if (filter === "clan" && !clan.trim()) return;
    const id = window.setTimeout(async () => {
      try {
        const qs = `filter=${encodeURIComponent(filter)}${filter === "clan" ? `&clan=${encodeURIComponent(clan)}` : ""}`;
        setCount(await apiGet<{ count: number; audience: string }>(`/admin/mass/count?${qs}`));
      } catch (e) {
        if (filter === "clan") toast(e instanceof Error ? e.message : String(e), "err");
      }
    }, 400);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, clan]);

  const content = { ...audience, text, photo_url: photo.trim() || null, button: button.trim() || null };
  const n = parseSigned(amount);
  return (
    <div className="adm-split">
      <Seg value={mode} onChange={setMode} options={[{ value: "broadcast", label: "Рассылка" }, { value: "grant", label: "Массовая выдача" }]} cols={2} />
      <Panel title="Кому">
        <Seg value={filter} onChange={setFilter} options={c.mass_filters.map((f) => ({ value: f.code, label: f.name }))} cols={2} />
        {filter === "clan" && (
          <Field label="Клан">
            <TextInput value={clan} onChange={setClan} placeholder="Название или id клана" />
          </Field>
        )}
        <div className="adm-hint">{count ? `${count.audience}: ${fmt(count.count)} игроков` : "Считаю получателей…"}</div>
      </Panel>
      {mode === "broadcast" ? (
        <Panel title="Сообщение">
          <Field label="Текст (можно HTML-теги Telegram: <b>, <i>, <a href>)">
            <textarea className="adm-textarea" value={text} onChange={(e) => setText(e.currentTarget.value)} placeholder="Текст рассылки" />
          </Field>
          <Field label="Картинка (необязательно)">
            <TextInput value={photo} onChange={setPhoto} placeholder="https://… ссылка на картинку" />
          </Field>
          <Field label="Кнопка (необязательно)">
            <TextInput value={button} onChange={setButton} placeholder="Текст | https://ссылка" />
          </Field>
          <div className="grid-2" style={{ gap: 8 }}>
            <button type="button" className="btn ghost" disabled={busy || (!text.trim() && !photo.trim())} onClick={() => run("/admin/mass/broadcast", { ...content, preview: true })}>
              Предпросмотр в бот
            </button>
            <ConfirmButton tone="gold" disabled={busy || !count || (!text.trim() && !photo.trim())} onConfirm={() => run("/admin/mass/broadcast", { ...content, preview: false })}>
              Отправить {count ? fmt(count.count) : ""}
            </ConfirmButton>
          </div>
        </Panel>
      ) : (
        <Panel title="Что выдать">
          <Field label="Ресурс">
            <Select value={resource} onChange={setResource} options={c.resources.map((r) => ({ value: r.code, label: r.name }))} />
          </Field>
          <Field label={`Количество каждому (до ${fmt(c.mass_max_amount)})`}>
            <TextInput type="number" value={amount} onChange={setAmount} placeholder="1000" />
          </Field>
          <ConfirmButton tone="gold" disabled={busy || !count || !n || n <= 0} onConfirm={() => run("/admin/mass/grant", { ...audience, resource, amount: n })}>
            Выдать всем {count ? fmt(count.count) : ""}
          </ConfirmButton>
        </Panel>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- промокоды

export function PromoSection() {
  const data = useApi<{ items: AdminPromo[]; resources: string[]; resource_labels?: Record<string, string> }>("/admin/promo");
  const { run, busy } = useAction(data.reload);
  const [open, setOpen] = useState<number | null>(null);
  // Форма как в UAP (пользователь 2026-10-21): поля вместо одной строки. Отправляем ту же строку
  // `КОД [uses|time|users] ПАРАМ ресурс:кол ...` — проверка и создание остаются на сервере.
  const [code, setCode] = useState("");
  const [mode, setMode] = useState<"uses" | "time" | "users" | "none">("uses");
  const [param, setParam] = useState("100");
  const [reward, setReward] = useState<Record<string, string>>({});
  const parts = Object.entries(reward).filter(([, v]) => Number(v)).map(([k, v]) => `${k}:${Math.trunc(Number(v))}`);
  const line = [code.trim().toUpperCase(), mode === "none" ? "" : `${mode} ${param.trim()}`, ...parts].filter(Boolean).join(" ");
  const ready = !!code.trim() && parts.length > 0 && (mode === "none" || !!param.trim());
  const create = async () => {
    if (await run("/admin/promo", { line })) {
      setCode("");
      setReward({});
    }
  };
  return (
    <Screen status={data.status} error={data.error}>
      {data.data && (
        <div className="adm-split">
          <Panel title="Новый промокод">
            <div className="adm-inline">
              <TextInput value={code} onChange={setCode} placeholder="КОД" />
            </div>
            <div className="adm-inline" style={{ marginTop: 8 }}>
              <Select value={mode} onChange={setMode} options={[
                { value: "uses", label: "По активациям" },
                { value: "time", label: "По времени (ч)" },
                { value: "users", label: "Для @username" },
                { value: "none", label: "Без лимита" },
              ]} />
              {mode !== "none" && (
                <TextInput value={param} onChange={setParam} placeholder={mode === "users" ? "@a,@b" : mode === "time" ? "часов" : "активаций"} />
              )}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 6, marginTop: 8 }}>
              {data.data.resources.map((r) => (
                <TextInput key={r} type="number" value={reward[r] ?? ""} onChange={(v) => setReward({ ...reward, [r]: v })}
                  placeholder={data.data?.resource_labels?.[r] ?? r} />
              ))}
            </div>
            <div className="adm-hint" style={{ marginTop: 6 }}>
              Отрицательная награда — штраф (баланс не уйдёт ниже 0). Итог: <code>{line || "—"}</code>
            </div>
            <button type="button" className="btn gold block" style={{ marginTop: 8 }} disabled={busy || !ready} onClick={create}>Создать</button>
          </Panel>
          <Panel title="Последние коды">
            <div className="adm-list">
              {data.data.items.map((p) => (
                <div key={p.id}>
                  <button type="button" className={`adm-item ${p.alive ? "" : "off"} ${open === p.id ? "on" : ""}`} onClick={() => setOpen(open === p.id ? null : p.id)}>
                    <div>
                      <b>{p.code}{p.alive ? <span className="adm-tag green">активен</span> : <span className="adm-tag red">{p.active ? "истёк" : "выключен"}</span>}</b>
                      <small>{p.reward.map((r) => `${r.amount > 0 ? "+" : "−"}${r.label}`).join(", ")}</small>
                    </div>
                    <div className="adm-right">{p.used}{p.max_uses != null ? `/${p.max_uses}` : ""}</div>
                  </button>
                  {open === p.id && (
                    <div style={{ display: "grid", gap: 8, margin: "8px 0" }}>
                      <Kv rows={[
                        ["Создан", when(p.created_at)], ["Срок", p.expires_at ? when(p.expires_at) : "без срока"],
                        ["Только для", p.users?.length ? p.users.map((u) => `@${u}`).join(", ") : "всех"],
                      ]} />
                      <div className="grid-2" style={{ gap: 6 }}>
                        <button type="button" className="btn ghost small" disabled={busy} onClick={() => run(`/admin/promo/${p.id}/active`, { active: !p.active })}>
                          {p.active ? "Выключить" : "Включить"}
                        </button>
                        <ConfirmButton small disabled={busy} onConfirm={() => run(`/admin/promo/${p.id}/delete`)}>Удалить</ConfirmButton>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {!data.data.items.length && <div className="adm-hint">Промокодов пока нет.</div>}
            </div>
          </Panel>
        </div>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- рефералы

export function ReferralSection() {
  const data = useApi<{ items: AdminReferral[]; name_max: number }>("/admin/referral");
  const { run, busy } = useAction(data.reload);
  const [name, setName] = useState("");
  const toast = useToast();
  return (
    <Screen status={data.status} error={data.error}>
      {data.data && (
        <div className="adm-split">
          <Panel title="Новая кампания">
            <div className="adm-inline">
              <TextInput value={name} onChange={setName} placeholder={`Название (до ${data.data.name_max})`} />
              <button type="button" className="btn small" disabled={busy || !name.trim()} onClick={async () => { if (await run("/admin/referral", { name })) setName(""); }}>Создать</button>
            </div>
          </Panel>
          <Panel title="Кампании">
            <div className="adm-list">
              {data.data.items.map((r) => (
                <div key={r.id} className="adm-item" style={{ display: "block" }}>
                  <div className="row">
                    <b>{r.name}</b>
                    <span className="adm-right">{fmt(r.visits)} переходов</span>
                  </div>
                  <button type="button" className="adm-code" style={{ border: "none", cursor: "pointer", margin: "6px 0", display: "block", textAlign: "left" }}
                    onClick={() => { void navigator.clipboard?.writeText(r.link); toast("Ссылка скопирована", "ok"); }}>
                    {r.link}
                  </button>
                  <small>
                    пришло {fmt(r.stats.came ?? 0)} · играют {fmt(r.stats.playing ?? 0)} · донатеров {fmt(r.stats.donors ?? 0)} · донат {fmt(r.stats.donated ?? 0)} ₽ · пасс {fmt(r.stats.bp ?? 0)}
                  </small>
                  <div style={{ marginTop: 8 }}>
                    <ConfirmButton small disabled={busy} onConfirm={() => run(`/admin/referral/${r.id}/delete`)}>Удалить</ConfirmButton>
                  </div>
                </div>
              ))}
              {!data.data.items.length && <div className="adm-hint">Кампаний пока нет.</div>}
            </div>
          </Panel>
        </div>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- события

export function EventsSection({ meta }: { meta: AdminMeta }) {
  const data = useApi<{ items: AdminEvent[] }>("/admin/events");
  const { run, busy } = useAction(data.reload);
  const kinds = meta.catalog.event_kinds;
  const [kind, setKind] = useState(kinds[0]?.key ?? "b");
  const [idx, setIdx] = useState(0);
  const [push, setPush] = useState(true);
  const kindDef = kinds.find((k) => k.key === kind);
  return (
    <Screen status={data.status} error={data.error}>
      {data.data && (
        <div className="adm-split">
          <Panel title="Идут сейчас">
            <div className="adm-list">
              {data.data.items.map((e) => (
                <div key={e.id} className="adm-item">
                  <div>
                    <b>{e.title}</b>
                    <small>{e.kind_name} · ещё {countdown(e.left_seconds)} · участников {e.entries}{e.clan_id ? ` · клан ${e.clan_id}` : ""}</small>
                  </div>
                  <ConfirmButton small tone="ghost" disabled={busy} onConfirm={() => run(`/admin/events/${e.id}/remove`)}>Снять</ConfirmButton>
                </div>
              ))}
              {!data.data.items.length && <div className="adm-hint">Событий нет.</div>}
            </div>
          </Panel>
          <Panel title="Запустить">
            <Seg value={kind} onChange={(k) => { setKind(k); setIdx(0); }} options={kinds.map((k) => ({ value: k.key, label: k.title }))} cols={3} />
            {kindDef && (
              <Field label="Кто">
                <Select value={idx} onChange={setIdx} options={kindDef.items.map((i) => ({ value: i.idx, label: i.name }))} />
              </Field>
            )}
            <Seg value={push ? "1" : "0"} onChange={(v) => setPush(v === "1")} options={[{ value: "1", label: "С пушами" }, { value: "0", label: "Без пушей" }]} cols={2} />
            <ConfirmButton tone="gold" disabled={busy} onConfirm={() => run("/admin/events/spawn", { kind, idx, push })}>Запустить событие</ConfirmButton>
          </Panel>
        </div>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- мир

interface CountryRow {
  code: string;
  name: string;
  cities: number;
  owned: number;
  bots: number;
  emperor: { id: number; label: string } | null;
}

interface CountryCity {
  id: number;
  name: string;
  districts: number;
  bots: number;
  owners: number;
  emperor: { id: number; label: string } | null;
}

/** Полоса «районы у игроков / у ботов» (доля игроков — акцентом). */
function OwnedBar({ owned, total }: { owned: number; total: number }) {
  return (
    <div className="bar" style={{ marginTop: 6 }}>
      <div className="fill-violet" style={{ width: `${total ? (owned / total) * 100 : 0}%` }} />
    </div>
  );
}

export function WorldSection() {
  const [country, setCountry] = useState<string | null>(null);
  const [cityId, setCityId] = useState<number | null>(null);
  const [found, setFound] = useState<{ id: number; name: string; country: string }[] | null>(null);
  const toast = useToast();
  const search = async (q: string) => {
    try {
      const r = await apiGet<{ items: { id: number; name: string; country: string }[] }>(`/admin/world/cities?q=${encodeURIComponent(q)}`);
      setFound(r.items);
      if (r.items.length === 1) {
        setCountry(r.items[0].country);
        setCityId(r.items[0].id);
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "err");
    }
  };
  return (
    <div className="adm-split">
      <Panel title="Поиск города">
        <SearchBox placeholder="Название города" onSearch={search} />
        {found && found.length !== 1 && (
          <div className="adm-list" style={{ marginTop: 10 }}>
            {found.map((c) => (
              <button key={c.id} type="button" className="adm-item" onClick={() => { setCountry(c.country); setCityId(c.id); setFound(null); }}>
                <b>{c.name}</b>
                <span className="adm-right">{c.country}</span>
              </button>
            ))}
            {!found.length && <div className="adm-hint">Не нашлось.</div>}
          </div>
        )}
      </Panel>
      {(country || cityId) && (
        <div className="adm-inline">
          <button type="button" className="btn ghost small" onClick={() => { setCountry(null); setCityId(null); }}>Все страны</button>
          {country && cityId && <button type="button" className="btn ghost small" onClick={() => setCityId(null)}>Города страны</button>}
        </div>
      )}
      {!country && !cityId && <Countries onPick={setCountry} />}
      {country && !cityId && <CountryCities code={country} onPick={setCityId} />}
      {cityId && <CityCard cityId={cityId} />}
    </div>
  );
}

function Countries({ onPick }: { onPick: (code: string) => void }) {
  const data = useApi<{ items: CountryRow[] }>("/admin/world/countries");
  return (
    <Screen status={data.status} error={data.error}>
      {data.data && (
        <div className="grid-2" style={{ gap: 8 }}>
          {data.data.items.map((c) => (
            <button key={c.code} type="button" className="tile" style={{ font: "inherit", textAlign: "left" }} onClick={() => onPick(c.code)}>
              <b>{c.name}</b>
              <small>{c.cities} городов · {fmt(c.owned)}/{fmt(c.owned + c.bots)} районов у игроков</small>
              <OwnedBar owned={c.owned} total={c.owned + c.bots} />
              <small style={{ marginTop: 6 }}>{c.emperor ? `император ${c.emperor.label}` : "без императора"}</small>
            </button>
          ))}
        </div>
      )}
    </Screen>
  );
}

function CountryCities({ code, onPick }: { code: string; onPick: (id: number) => void }) {
  const data = useApi<{ name: string; cities: CountryCity[] }>(`/admin/world/countries/${code}`);
  const [filter, setFilter] = useState<"all" | "contested" | "bots">("all");
  const d = data.data;
  const list = d?.cities.filter((c) => filter === "all" || (filter === "bots" ? c.bots === c.districts : c.owners > 1)) ?? [];
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <Panel title={d.name}>
          <Seg value={filter} onChange={setFilter} options={[{ value: "all", label: "Все" }, { value: "contested", label: "Делят игроки" }, { value: "bots", label: "Только боты" }]} cols={3} />
          <div className="adm-list">
            {list.map((c) => (
              <button key={c.id} type="button" className="adm-item" style={{ display: "block" }} onClick={() => onPick(c.id)}>
                <div className="row">
                  <b>{c.name}</b>
                  <span className="adm-right">{fmt(c.districts - c.bots)}/{fmt(c.districts)}</span>
                </div>
                <OwnedBar owned={c.districts - c.bots} total={c.districts} />
                <small>
                  {c.emperor ? `император ${c.emperor.label} · ` : ""}владельцев {c.owners}{c.bots ? ` · у ботов ${c.bots}` : ""}
                </small>
              </button>
            ))}
            {!list.length && <div className="adm-hint">Нет городов под фильтр.</div>}
          </div>
        </Panel>
      )}
    </Screen>
  );
}

function CityCard({ cityId }: { cityId: number }) {
  const data = useApi<AdminCity>(`/admin/world/cities/${cityId}`);
  const { run, busy } = useAction(data.reload);
  const [district, setDistrict] = useState<number | null>(null);
  const [owner, setOwner] = useState("");
  const [emperor, setEmperor] = useState("");
  const d = data.data;
  const sel = d?.districts.find((x) => x.id === district);
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <>
          <Panel title={`${d.name} · ${d.country}`}>
            <Kv rows={[
              ["Император", d.emperor ? <Link to={adminPlayerPath(d.emperor.id)} style={{ color: "inherit" }}>{d.emperor.label}</Link> : "—"],
              ["Районов", `${d.districts.length} (у ботов ${d.districts.filter((x) => x.owner_id == null).length})`],
              ["Вызовов в ожидании", d.pending_challenges], ["Войн императора", d.pending_wars],
            ]} />
            <OwnerSummary districts={d.districts} />
            <div className="adm-hint" style={{ marginTop: 10 }}>Район:</div>
            <div className="adm-grid-btn">
              {d.districts.map((x) => (
                <button key={x.id} type="button" className={`btn small ${district === x.id ? "" : x.owner_id ? "violet" : "ghost"}`} onClick={() => setDistrict(x.id)}>{x.number}</button>
              ))}
            </div>
          </Panel>
          {sel && (
            <Panel title={`Район №${sel.number}`}>
              <Kv rows={[
                ["Владелец", sel.owner_id ? <Link to={adminPlayerPath(sel.owner_id)} style={{ color: "inherit" }}>{sel.owner}</Link> : "боты"],
                ["Вызов", sel.challenge ? `${sel.challenge.attacker_id} → ${sel.challenge.defender_id}` : "нет"],
              ]} />
              <div className="adm-inline" style={{ marginTop: 10 }}>
                <TextInput value={owner} onChange={setOwner} placeholder="@nick или id нового владельца" />
                <button type="button" className="btn small" disabled={busy || !owner.trim()} onClick={async () => { if (await run(`/admin/world/districts/${sel.id}/owner`, { query: owner })) setOwner(""); }}>Передать</button>
              </div>
              {sel.owner_id != null && (
                <div style={{ marginTop: 8 }}>
                  <ConfirmButton disabled={busy} onConfirm={() => run(`/admin/world/districts/${sel.id}/reset`)}>Вернуть ботам</ConfirmButton>
                </div>
              )}
            </Panel>
          )}
          <Panel title="Император и вызовы">
            <div className="adm-inline" style={{ marginBottom: 8 }}>
              <TextInput value={emperor} onChange={setEmperor} placeholder="@nick или id" />
              <button type="button" className="btn gold small" disabled={busy || !emperor.trim()} onClick={async () => { if (await run(`/admin/world/cities/${d.id}/emperor`, { query: emperor })) setEmperor(""); }}>Назначить</button>
            </div>
            <div className="adm-split">
              {d.emperor && <ConfirmButton disabled={busy} onConfirm={() => run(`/admin/world/cities/${d.id}/emperor/remove`)}>Снять императора</ConfirmButton>}
              {d.emperor && d.pending_wars > 0 && <ConfirmButton tone="ghost" disabled={busy} onConfirm={() => run(`/admin/world/cities/${d.id}/wars/cancel`)}>Отменить войны императора ({d.pending_wars})</ConfirmButton>}
              {d.pending_challenges > 0 && <ConfirmButton tone="ghost" disabled={busy} onConfirm={() => run(`/admin/world/cities/${d.id}/challenges/cancel`)}>Отменить вызовы ({d.pending_challenges})</ConfirmButton>}
            </div>
          </Panel>
        </>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- кланы

export function ClansSection() {
  const [items, setItems] = useState<{ id: number; name: string }[] | null>(null);
  const [clanId, setClanId] = useState<number | null>(null);
  const toast = useToast();
  const search = async (q: string) => {
    try {
      const r = await apiGet<{ items: { id: number; name: string }[] }>(`/admin/clans?q=${encodeURIComponent(q)}`);
      setItems(r.items);
      setClanId(r.items.length === 1 ? r.items[0].id : null);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "err");
    }
  };
  return (
    <div className="adm-split">
      <Panel title="Клан">
        <SearchBox placeholder="Название или id клана" onSearch={search} />
        {items && !clanId && (
          <div className="adm-list" style={{ marginTop: 10 }}>
            {items.map((c) => (
              <button key={c.id} type="button" className="adm-item" onClick={() => setClanId(c.id)}>
                <b>{c.name}</b>
                <span className="adm-right">id {c.id}</span>
              </button>
            ))}
            {!items.length && <div className="adm-hint">Не нашлось.</div>}
          </div>
        )}
      </Panel>
      {clanId && <ClanCard clanId={clanId} onDeleted={() => { setClanId(null); setItems(null); }} />}
    </div>
  );
}

function ClanCard({ clanId, onDeleted }: { clanId: number; onDeleted: () => void }) {
  const data = useApi<AdminClan>(`/admin/clans/${clanId}`);
  const { run, busy } = useAction(data.reload);
  const [lands, setLands] = useState("");
  const [donate, setDonate] = useState("");
  const [transfer, setTransfer] = useState<number | null>(null);
  const d = data.data;
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <>
          <Panel title={d.name}>
            <Kv rows={[
              ["Владелец", <Link to={adminPlayerPath(d.owner_id)} style={{ color: "inherit" }}>{d.owner}</Link>],
              ["Земли", `${d.lands} (${d.limits.lands_min}…${d.limits.lands_max})`], ["Казна", fmt(d.treasury)],
              ["Уровень клана", `${d.donate_level}/${d.limits.donate_max}`], ["Мощь роты", fmt(d.power)],
              ["Щит", d.shield_seconds ? countdown(d.shield_seconds) : "нет"], ["КД войны", d.cooldown_seconds ? countdown(d.cooldown_seconds) : "нет"],
              ["Клановый донат", `${d.buyers} покупателей · ${fmt(d.paid)} 💎`],
            ]} />
          </Panel>
          <Panel title="Изменить">
            <Field label="Земли">
              <div className="adm-inline">
                <TextInput type="number" value={lands} onChange={setLands} placeholder={String(d.lands)} />
                <button type="button" className="btn small" disabled={busy || parseSigned(lands) == null} onClick={async () => { if (await run(`/admin/clans/${d.id}/value`, { field: "lands", value: parseSigned(lands) })) setLands(""); }}>Задать</button>
              </div>
            </Field>
            <Field label="Казна">
              <GiveTakeForm busy={busy} onSubmit={(delta) => run(`/admin/clans/${d.id}/value`, { field: "treasury", value: delta })} />
            </Field>
            <Field label="Уровень клана">
              <div className="adm-inline">
                <TextInput type="number" value={donate} onChange={setDonate} placeholder={String(d.donate_level)} />
                <button type="button" className="btn small" disabled={busy || parseSigned(donate) == null} onClick={async () => { if (await run(`/admin/clans/${d.id}/value`, { field: "donate", value: parseSigned(donate) })) setDonate(""); }}>Задать</button>
              </div>
            </Field>
            <div className="grid-2" style={{ gap: 6 }}>
              <button type="button" className="btn ghost small" disabled={busy || !d.shield_seconds} onClick={() => run(`/admin/clans/${d.id}/shield`)}>Снять щит</button>
              <button type="button" className="btn ghost small" disabled={busy || !d.cooldown_seconds} onClick={() => run(`/admin/clans/${d.id}/cooldown`)}>Снять КД войны</button>
            </div>
          </Panel>
          <Panel title={`Участники · ${d.members.length}`}>
            <div className="adm-list">
              {d.members.map((m) => (
                <div key={m.id} className={`adm-item ${transfer === m.id ? "on" : ""}`}>
                  <Link to={adminPlayerPath(m.id)} style={{ color: "inherit", textDecoration: "none", minWidth: 0 }}>
                    <b>{m.label}</b>
                    <small>{m.rank}</small>
                  </Link>
                  {m.id !== d.owner_id && (
                    <button type="button" className="btn ghost small" onClick={() => setTransfer(transfer === m.id ? null : m.id)}>Владелец</button>
                  )}
                </div>
              ))}
            </div>
            {transfer && (
              <div style={{ marginTop: 10 }}>
                <ConfirmButton tone="gold" disabled={busy} onConfirm={async () => { if (await run(`/admin/clans/${d.id}/transfer`, { user_id: transfer })) setTransfer(null); }}>
                  Передать клан выбранному
                </ConfirmButton>
              </div>
            )}
          </Panel>
          <Panel title="Удаление" tone="red">
            <div className="adm-hint">Клан распускается, клановый донат возвращается купившим.</div>
            <ConfirmButton disabled={busy} onConfirm={async () => { const r = await run(`/admin/clans/${d.id}/delete`); if (r?.deleted) onDeleted(); }}>Удалить клан</ConfirmButton>
          </Panel>
        </>
      )}
    </Screen>
  );
}

// ---------------------------------------------------------------- сезон пасса и задания

export function SeasonSection() {
  const data = useApi<AdminSeason>("/admin/season");
  const { run, busy } = useAction(data.reload);
  const [uid, setUid] = useState<number | null>(null);
  const toast = useToast();
  const find = async (q: string) => {
    try {
      setUid((await apiGet<{ id: number }>(`/admin/players/find?q=${encodeURIComponent(q)}`)).id);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "err");
    }
  };
  const d = data.data;
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <div className="adm-split">
          <Panel title={`Сезон №${d.number}`}>
            <Kv rows={[["Начало", when(d.starts_at)], ["Конец", when(d.ends_at)], ["Осталось", countdown(d.left_seconds)], ["Премиум у игроков", fmt(d.premium)]]} />
            <div style={{ marginTop: 10 }}>
              <ConfirmButton tone="gold" disabled={busy} onConfirm={() => run("/admin/season/new")}>Начать новый сезон</ConfirmButton>
            </div>
          </Panel>
          <Panel title="Игрок">
            <SearchBox placeholder="@nick или id" onSearch={find} />
          </Panel>
          {uid && <SeasonPlayer uid={uid} />}
        </div>
      )}
    </Screen>
  );
}

function SeasonPlayer({ uid }: { uid: number }) {
  const data = useApi<AdminSeasonPlayer>(`/admin/season/players/${uid}`);
  const { run, busy } = useAction(data.reload);
  const d = data.data;
  return (
    <Screen status={data.status} error={data.error}>
      {d && (
        <>
          <Panel title={d.label}>
            <Kv rows={[["Уровень", d.level], ["Опыт", fmt(d.xp)], ["Премиум", d.premium ? "да" : "нет"], ["Забрано", `бесплатно ${d.claimed_free} · премиум ${d.claimed_premium}`]]} />
            <Field label="Опыт пасса">
              <GiveTakeForm busy={busy} onSubmit={(delta) => run(`/admin/season/players/${uid}/xp`, { delta })} />
            </Field>
            <div className="grid-2" style={{ gap: 6 }}>
              <button type="button" className={`btn small ${d.premium ? "gold" : "ghost"}`} disabled={busy} onClick={() => run(`/admin/season/players/${uid}/premium`)}>
                Премиум: {d.premium ? "вкл" : "выкл"}
              </button>
              <ConfirmButton small tone="ghost" disabled={busy} onConfirm={() => run(`/admin/season/players/${uid}/reset`)}>Сбросить награды</ConfirmButton>
            </div>
          </Panel>
          <Panel title="Задания дня">
            <div className="adm-list">
              {d.quests.map((q) => (
                <div key={q.slot} className={`adm-item ${q.done ? "off" : ""}`}>
                  <div>
                    <b>#{q.slot} {q.task}</b>
                    <small>{fmt(q.progress)} / {fmt(q.target)} · {q.xp} опыта</small>
                  </div>
                  {!q.done && <button type="button" className="btn small" disabled={busy} onClick={() => run(`/admin/season/players/${uid}/quest`, { slot: q.slot })}>Засчитать</button>}
                </div>
              ))}
            </div>
            <div style={{ marginTop: 10 }}>
              <ConfirmButton tone="ghost" disabled={busy} onConfirm={() => run(`/admin/season/players/${uid}/reroll`)}>Новый набор заданий</ConfirmButton>
            </div>
          </Panel>
        </>
      )}
    </Screen>
  );
}


/** Кто сколько районов держит в городе (крупнейшие — сверху). */
function OwnerSummary({ districts }: { districts: AdminCity["districts"] }) {
  const groups = new Map<number | null, { label: string; count: number }>();
  for (const x of districts) {
    const g = groups.get(x.owner_id) ?? { label: x.owner ?? "Боты", count: 0 };
    g.count += 1;
    groups.set(x.owner_id, g);
  }
  const rows = [...groups.entries()].sort((a, b) => b[1].count - a[1].count);
  return (
    <div className="adm-list" style={{ marginTop: 10 }}>
      {rows.map(([id, g]) => (
        <div key={String(id)} className="adm-item" style={{ display: "block" }}>
          <div className="row">
            {id ? <Link to={adminPlayerPath(id)} style={{ color: "inherit" }}><b>{g.label}</b></Link> : <b className="muted">{g.label}</b>}
            <span className="adm-right">{g.count}</span>
          </div>
          <OwnedBar owned={g.count} total={districts.length} />
        </div>
      ))}
    </div>
  );
}
