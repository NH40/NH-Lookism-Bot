import { Building2, ChevronLeft, ChevronRight, Crown, Flag, Skull, Swords, Trophy, UserPlus, Users, Layers } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { imgUrl } from "../../api";
import type { BattleResult, BossResult, ChallengeResult, DistrictCard, MapData, MapDistrict, MapEvent } from "../../types";
import { Panel, Screen, StatRow, countdown, fmt, useCountdown } from "../../components/ui";
import { PHASE_CIRCLE, PHASE_FIST, ROUTE_BUSINESS, ROUTE_CARDS, ROUTE_COUNTRY, ROUTE_EMPIRE, ROUTE_DEVELOPMENT, ROUTE_GANG, ROUTE_MAP_EVENTS, ROUTE_TRAINING } from "../../constants/constants";
import { useAction, useApi } from "../../hooks/useApi";
import { Sheet } from "../../components/Sheet";
import { Journal } from "../../components/Journal";
import "../../styles/game-screens.css";

type Outcome =
  | { kind: "battle"; data: BattleResult }
  | { kind: "boss"; data: BossResult }
  | { kind: "challenge"; data: ChallengeResult };

function ResultView({ outcome, onClose }: { outcome: Outcome; onClose: () => void }) {
  if (outcome.kind === "challenge") {
    const d = outcome.data;
    return (
      <>
        <div className="res-head"><Swords size={20} />Вызов брошен</div>
        <p className="muted" style={{ fontSize: 13, fontWeight: 600, margin: "0 0 12px" }}>{d.message}</p>
        <button className="btn block" type="button" onClick={onClose}>Понятно</button>
      </>
    );
  }
  if (outcome.kind === "boss") {
    const d = outcome.data;
    return (
      <>
        <div className={`res-head ${d.won ? "win" : "lose"}`}>
          {d.won ? <Trophy size={20} /> : <Skull size={20} />}
          {d.won ? "Босс повержен" : "Босс устоял"}
        </div>
        <div className="muted" style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>{d.message}</div>
        <StatRow label="Раундов" value={d.rounds} />
        <StatRow label="Твоя мощь" value={fmt(d.attacker_power)} />
        <StatRow label="Твои потери" value={fmt(d.attacker_dead)} />
        <StatRow label="Мощь босса" value={fmt(d.boss_power)} />
        <StatRow label="Осталось у босса" value={fmt(d.boss_remaining_power)} />
        {d.fragments > 0 && <StatRow label={`+ ${d.fragment_name}`} value={d.fragments} />}
        <Journal lines={d.journal} />
        <button className="btn block" type="button" style={{ marginTop: 12 }} onClick={onClose}>Закрыть</button>
      </>
    );
  }
  const d = outcome.data;
  return (
    <>
      <div className={`res-head ${d.captured ? "win" : "lose"}`}>
        {d.captured ? <Flag size={20} /> : <Skull size={20} />}
        {d.message}
      </div>
      <StatRow label="Раундов" value={d.rounds} />
      <StatRow label="Твоя армия" value={`${fmt(d.attacker_quantity)} · мощь ${fmt(d.attacker_power)}`} />
      <StatRow label="Потери" value={fmt(d.attacker_dead)} />
      <StatRow label="Сбежали" value={fmt(d.attacker_fled)} />
      <StatRow label="Осталось мощи" value={fmt(d.attacker_remaining_power)} />
      <StatRow label="Мощь ботов" value={fmt(d.defender_power)} />
      <StatRow label="Потери ботов" value={fmt(d.defender_dead)} />
      <Journal lines={d.journal} />
      <StatRow label="Влияние" value={d.influence} />
      {d.promoted && <p className="muted" style={{ fontSize: 12, fontWeight: 700 }}>{d.promoted}</p>}
      {d.free_attack && <p className="muted" style={{ fontSize: 12, fontWeight: 700 }}>Ловкость: КД после этой атаки не поставлен.</p>}
      {d.throne && (
        <p className="muted" style={{ fontSize: 12, fontWeight: 700 }}>
          Бой за трон с {d.throne.incumbent}: {d.throne.contender_won ? "победа" : "поражение"} ({d.throne.rounds} р.)
        </p>
      )}
      <button className="btn block" type="button" style={{ marginTop: 12 }} onClick={onClose}>Закрыть</button>
    </>
  );
}

function DistrictSheet({ district, onClose, onChanged }: { district: MapDistrict; onClose: () => void; onChanged: () => void }) {
  const card = useApi<DistrictCard>(`/district/${district.id}`);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const { run, busy } = useAction(onChanged);
  const cd = useCountdown(card.data?.cooldown_seconds ?? 0);

  const fight = async (action: "attack" | "challenge") => {
    const result = await run(`/district/${district.id}/${action}`);
    if (result) setOutcome({ kind: action === "attack" ? "battle" : "challenge", data: result as never });
    else await card.reload();
  };

  const d = card.data;
  return (
    <Sheet title={`Район №${district.number}`} onClose={onClose}>
      {outcome ? (
        <ResultView outcome={outcome} onClose={onClose} />
      ) : !d ? (
        <div className="skeleton" style={{ height: 160 }} />
      ) : (
        <>
          <div className="muted" style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>
            {d.kind === "mine" ? "Твой район" : d.kind === "bot" ? "Район держат боты" : `Владелец: ${d.owner}`}
          </div>
          {d.kind === "bot" && (
            <>
              <StatRow label="Ранг ботов" value={d.bot_rank ?? "—"} />
              <StatRow label="Бойцов у ботов" value={fmt(d.bot_quantity ?? 0)} />
              <StatRow label="Мощь ботов" value={fmt(d.bot_power ?? 0)} />
            </>
          )}
          {d.kind !== "mine" && (
            <>
              <StatRow label="Твой лагерь атаки" value={`${fmt(d.attack_quantity)} · мощь ${fmt(d.attack_power)}`} />
              <StatRow label="КД сражения" value={cd > 0 ? countdown(cd) : "готов"} />
            </>
          )}
          {d.kind === "player" && <StatRow label="Окно принятия вызова" value={`${d.accept_window_minutes} мин.`} />}
          {d.blocked_reason && <p className="muted" style={{ fontSize: 12, fontWeight: 700 }}>{d.blocked_reason}</p>}
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
            {d.kind === "bot" && (
              <button className={`btn red block ${!d.can_act || cd > 0 ? "off" : ""}`} type="button" disabled={busy || !d.can_act || cd > 0} onClick={() => fight("attack")}>
                <Swords size={16} />Атаковать ботов
              </button>
            )}
            {d.kind === "player" && (
              <button className={`btn red block ${!d.can_act || cd > 0 ? "off" : ""}`} type="button" disabled={busy || !d.can_act || cd > 0} onClick={() => fight("challenge")}>
                <Swords size={16} />Бросить вызов игроку
              </button>
            )}
            {d.kind === "mine" && (
              <Link className="btn block" to={ROUTE_BUSINESS}><Building2 size={16} />Открыть бизнесы</Link>
            )}
          </div>
        </>
      )}
    </Sheet>
  );
}

function EventCard({ event, onFight, onMeet, busy, bossCd }: {
  event: MapEvent; onFight: (e: MapEvent) => void; onMeet: (e: MapEvent) => void; busy: boolean; bossCd: number;
}) {
  const left = useCountdown(event.ends_in_seconds);
  if (event.kind === "boss") {
    return (
      <div className="boss-card">
        {event.image && <img src={imgUrl(event.image, 480)} alt={event.title} loading="lazy" />}
        <div className="boss-over">
          <div className="boss-tag">БОСС НА КАРТЕ</div>
          <div className="disp" style={{ fontSize: 17, fontWeight: 800 }}>{event.title}</div>
          <div className="boss-desc">{event.subtitle} Исчезнет через {countdown(left)}.</div>
          <button className={`btn red ${event.won || bossCd > 0 ? "off" : ""}`} type="button" style={{ marginTop: "auto", width: 140 }} disabled={busy || event.won || bossCd > 0} onClick={() => onFight(event)}>
            {event.won ? "Побеждён" : bossCd > 0 ? `КД ${countdown(bossCd)}` : "В бой"}
          </button>
        </div>
      </div>
    );
  }
  // Учитель техник / школы: «Взять задание» (как кнопка под учителем в боте), дальше — куда сдавать.
  const target = event.kind === "school" ? ROUTE_TRAINING : ROUTE_DEVELOPMENT;
  const where = event.kind === "school" ? "Тренировки" : "Развитие";
  return (
    <div className="tile">
      <div className="event-row">
        <div className="ico-box"><Users size={18} /></div>
        <div>
          <b>Учитель: {event.title}</b>
          <small style={{ display: "block" }}>{event.subtitle} · {countdown(left)}</small>
        </div>
      </div>
      {event.state === "new" && (
        <button className="btn gold block small" type="button" style={{ marginTop: 8 }} disabled={busy} onClick={() => onMeet(event)}>
          Взять задание
        </button>
      )}
      {event.state === "active" && (
        <Link className={`btn block small ${event.quest_complete ? "green" : "ghost"}`} style={{ marginTop: 8 }} to={target}>
          {event.quest_complete ? `Задание выполнено — сдать (${where})` : `Задание взято — прогресс (${where})`}
        </Link>
      )}
      {event.state === "done" && (
        <Link className="btn ghost block small" style={{ marginTop: 8 }} to={target}>
          {event.kind === "school" ? "Учитель уже открыт" : "Техника уже изучена"}
        </Link>
      )}
    </div>
  );
}

export function MapPage() {
  const [page, setPage] = useState(0);
  const { data, status, error, reload } = useApi<MapData>(`/map?page=${page}`);
  const [selected, setSelected] = useState<MapDistrict | null>(null);
  const [bossOutcome, setBossOutcome] = useState<BossResult | null>(null);
  const { run, busy } = useAction(reload);
  const cd = useCountdown(data?.attack_cooldown_seconds ?? 0);
  const bossCd = useCountdown(data?.boss_cooldown_seconds ?? 0);

  const meetTeacher = async (e: MapEvent) => {
    await run(`/map/events/${e.id}/meet`);
  };

  const fightBoss = async (e: MapEvent) => {
    const result = await run(`/boss/${e.id}/fight`);
    if (result) setBossOutcome(result as never);
  };

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <div className="map-hero">
            {data.city.art && <img src={imgUrl(data.city.art, 720)} alt={data.city.name} />}
            <div className="map-hero-over">
              <div className="disp" style={{ fontSize: 20, fontWeight: 800 }}>{data.city.name}</div>
              <div className="map-hero-meta">
                <span className="muted">{data.city.country_name ?? ""} · {data.city.district_count} районов</span>
                {data.emperor && (
                  <span className="map-emperor"><Crown size={14} />Император: {data.emperor.name} · налог {data.emperor.tax_percent}%</span>
                )}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <div className="stat-tile"><span className="muted">Твои районы</span><div className="disp" style={{ color: "var(--cyan)" }}>{data.my_districts}</div></div>
            <div className="stat-tile"><span className="muted">Доход/мин</span><div className="disp" style={{ color: "var(--gold-2)" }}>+{fmt(Math.round(data.income_per_minute))}</div></div>
            <div className="stat-tile"><span className="muted">Атака через</span><div className="disp">{cd > 0 ? countdown(cd) : "готов"}</div></div>
          </div>

          <div className="grid-4">
            <Link className="qa" to={ROUTE_GANG}><Users size={20} color="var(--cyan-2)" />Банда</Link>
            <Link className="qa" to={ROUTE_CARDS}><Layers size={20} color="var(--cyan-2)" />Уники</Link>
            <Link className="qa" to={`${ROUTE_GANG}#recruit`}><UserPlus size={20} color="var(--cyan-2)" />Вербовка</Link>
            <Link className="qa" to={ROUTE_BUSINESS}><Building2 size={20} color="var(--gold-2)" />Бизнес</Link>
          </div>

          <Panel title="РАЙОНЫ">
            {data.sole_owner && (
              <p className="muted" style={{ margin: "0 0 10px", fontSize: 12, fontWeight: 700 }}>Весь город принадлежит: {data.sole_owner}</p>
            )}
            <div className="grid-4">
              {data.districts.map((d) => (
                <button key={d.id} type="button" className={`dist ${d.kind}`} onClick={() => setSelected(d)}>
                  {d.number}
                  <small>{d.kind === "mine" ? "твой" : d.kind === "bot" ? "боты" : d.owner}</small>
                </button>
              ))}
            </div>
            <div className="pager">
              <span>Показаны {data.page * 12 + 1}–{data.page * 12 + data.districts.length} из {data.total}</span>
              <span>
                <button type="button" disabled={data.page <= 0} onClick={() => setPage(data.page - 1)}><ChevronLeft size={14} />Назад</button>
                <button type="button" disabled={data.page >= data.pages - 1} onClick={() => setPage(data.page + 1)}>Далее<ChevronRight size={14} /></button>
              </span>
            </div>
            {!data.can_attack && !data.empire && (
              <p className="muted" style={{ margin: "8px 0 0", fontSize: 11, fontWeight: 700 }}>
                Твоя фаза воюет за город целиком — бои за города страны доступны в боте (Карта).
              </p>
            )}
          </Panel>

          {(data.phase === PHASE_CIRCLE || data.phase === PHASE_FIST) && (
            <Link to={ROUTE_COUNTRY} className="emp-entry country">
              <span className="ico"><Flag size={20} color="var(--cyan-2)" /></span>
              <span style={{ flex: 1, minWidth: 0 }}>
                <b>Карта страны</b>
                <small>{data.phase === PHASE_FIST ? "города страны · только просмотр" : "штурм ботов города и вызовы за город"}</small>
              </span>
              <ChevronRight size={18} />
            </Link>
          )}
          {(data.empire || data.emperor) && (
            <Link to={ROUTE_EMPIRE} className="emp-entry">
              <span className="ico" style={{ borderColor: "rgba(245,185,66,.6)", background: "rgba(245,185,66,.12)" }}><Crown size={20} color="var(--gold-2)" /></span>
              <span style={{ flex: 1, minWidth: 0 }}>
                <b>{data.empire ? "Твоя империя" : "Империя"}</b>
                <small>
                  {data.empire
                    ? `${fmt(data.empire.cities)} гор. · налог ${data.empire.tax_percent}% · война императоров`
                    : `${data.emperor?.name} · налог ${data.emperor?.tax_percent}% · саботаж`}
                </small>
              </span>
              <ChevronRight size={18} />
            </Link>
          )}

          {data.events.map((e) => (
            <EventCard key={e.id} event={e} onFight={fightBoss} onMeet={meetTeacher} busy={busy} bossCd={bossCd} />
          ))}
          <Link to={ROUTE_MAP_EVENTS} className="row" style={{ justifyContent: "center", gap: 4, color: "var(--cyan-2)", fontSize: 13, fontWeight: 800, textDecoration: "none", minHeight: 44 }}>
            Кто может появиться<ChevronRight size={16} />
          </Link>
        </div>
      )}

      {selected && <DistrictSheet district={selected} onClose={() => setSelected(null)} onChanged={reload} />}
      {bossOutcome && (
        <Sheet title={bossOutcome.boss_name} onClose={() => setBossOutcome(null)}>
          <ResultView outcome={{ kind: "boss", data: bossOutcome }} onClose={() => setBossOutcome(null)} />
        </Sheet>
      )}
    </Screen>
  );
}
