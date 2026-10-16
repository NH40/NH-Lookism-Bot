import { Crown, Gift, Map as MapIcon, Swords, Users } from "lucide-react";
import { useState } from "react";
import type { PlayersData, TopData, TopPlayer } from "../../types";
import { BackHeader, Panel, Screen, countdown, fmt, useCountdown } from "../../components/ui";
import { ROUTE_MORE } from "../../constants";
import { useApi } from "../../hooks/useApi";
import "./Top.css";

type Tab = "players" | "clans" | "all";
const TABS: { id: Tab; label: string }[] = [
  { id: "players", label: "Игроки" },
  { id: "clans", label: "Кланы" },
  { id: "all", label: "Все" },
];
const MEDAL: Record<number, string> = { 1: "gold", 2: "silver", 3: "bronze" };

function Place({ n }: { n: number }) {
  return <div className={`top-place ${MEDAL[n] ?? ""}`}>{n}</div>;
}

function PlayerRow({ p }: { p: TopPlayer }) {
  return (
    <div className={`top-row ${p.is_me ? "me" : ""}`}>
      <Place n={p.place} />
      <div className="grow">
        <div className="top-name">{p.name}{p.is_me ? " · ты" : ""}</div>
        <div className="muted top-sub">
          {p.phase}
          {p.clan ? ` · ${p.clan}` : ""}
        </div>
        {p.reward && <div className="top-reward"><Gift size={12} /> {p.reward}</div>}
      </div>
      <div className="top-power"><Swords size={13} /> {fmt(p.power)}</div>
    </div>
  );
}

function AllPlayers() {
  const [page, setPage] = useState(0);
  const { data, status, error } = useApi<PlayersData>(`/top/players?page=${page}`);
  return (
    <Screen status={status} error={error}>
      {data && (
        <Panel title={`Все игроки · ${fmt(data.total)}`}>
          {data.players.map((p) => <PlayerRow key={p.user_id} p={p} />)}
          {data.pages > 1 && (
            <div className="top-pager">
              <button className="btn ghost small" type="button" disabled={page <= 0} onClick={() => setPage(page - 1)}>Назад</button>
              <span className="muted">{data.page + 1}/{data.pages}</span>
              <button className="btn ghost small" type="button" disabled={page >= data.pages - 1} onClick={() => setPage(page + 1)}>Далее</button>
            </div>
          )}
        </Panel>
      )}
    </Screen>
  );
}

/** Топ игроков (мощь армии) и кланов (земли) с наградами сезона + список всех игроков. */
export function TopPage() {
  const [tab, setTab] = useState<Tab>("players");
  const { data, status, error } = useApi<TopData>("/top");
  const season = useCountdown(data?.season_ends_in ?? 0);
  return (
    <div className="page">
      <BackHeader title="Топ" to={ROUTE_MORE} />
      <div className="seg" role="tablist" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" className={`pill ${tab === t.id ? "on" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "all" ? (
        <AllPlayers />
      ) : (
        <Screen status={status} error={error}>
          {data && (
            <>
              <div className="grid-2">
                <div className="stat-tile">
                  <span className="muted">Твоё место</span>
                  <div className="disp">{data.my_place ? `#${data.my_place}` : "—"}</div>
                </div>
                <div className="stat-tile">
                  <span className="muted">Итог сезона</span>
                  <div className="disp">{data.season_ends_in ? countdown(season) : "—"}</div>
                </div>
              </div>
              {tab === "players" ? (
                <Panel title="Топ игроков · мощь армии" tone="gold">
                  {data.players.length === 0 ? <div className="muted top-hint">Пока пусто.</div> : data.players.map((p) => <PlayerRow key={p.user_id} p={p} />)}
                  <div className="muted top-hint">Мощь обновляется раз в 10 минут. Награды — по итогу сезона (раз в месяц) и при вайпе.</div>
                </Panel>
              ) : (
                <Panel title="Топ кланов · земли" tone="violet">
                  {data.clans.length === 0 ? (
                    <div className="muted top-hint">Кланов пока нет.</div>
                  ) : (
                    data.clans.map((c) => (
                      <div key={c.name} className="top-row">
                        <Place n={c.place} />
                        <div className="grow">
                          <div className="top-name">{c.name}</div>
                          <div className="muted top-sub">
                            <MapIcon size={11} /> {fmt(c.lands)} · <Users size={11} /> {c.members}
                          </div>
                          {c.reward && <div className="top-reward"><Gift size={12} /> {c.reward} каждому</div>}
                        </div>
                        {c.place === 1 && <Crown size={18} color="var(--gold-2)" />}
                      </div>
                    ))
                  )}
                  <div className="muted top-hint">Награда — каждому участнику клана: топ-3 — донат-коины, 4–5 места — NHCoin и тикеты.</div>
                </Panel>
              )}
            </>
          )}
        </Screen>
      )}
    </div>
  );
}
