import { Building2, ChevronRight, Crown, Flag, Luggage, Skull, Swords, Trophy, UserPlus, Users, Layers } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet, imgUrl } from "../../api";
import type { BattleResult, BossResult, ChallengeResult, DistrictCard, MapData, MapDistrict, MapEvent } from "../../types";
import { Panel, Screen, StatRow, countdown, fmt, useCountdown } from "../../components/ui";
import { PHASE_CIRCLE, PHASE_FIST, ROUTE_BUSINESS, ROUTE_CARDS, ROUTE_COUNTRY, ROUTE_EMPIRE, ROUTE_DEVELOPMENT, ROUTE_GANG, ROUTE_MAP_EVENTS, ROUTE_TRAINING, ROUTE_TRAVEL, battlePath } from "../../constants/constants";
import { useAction, useApi } from "../../hooks/useApi";
import { Sheet } from "../../components/Sheet";
import { Journal } from "../../components/Journal";
import "../../styles/game-screens.css";
import "../../styles/world-map.css";
import { RaidBanner } from "./RaidBanner";
import { OnlineBattleButton } from "../../components/OnlineBattleButton";
import { ChallengesPanel } from "./ChallengesPanel";
import { CityView } from "./CityView";
import { EventFeed } from "./EventFeed";
import { WorldMap } from "./WorldMap";
import type { Geo, LiveDistrict, WorldData } from "./worldTypes";

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

  const nav = useNavigate();
  const online = async () => {
    const r = (await run("/arena/start/district", { district_id: district.id })) as { id?: string } | null;
    if (r?.id) nav(battlePath(r.id));
  };
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
      ) : card.status === "error" ? (
        <>
          <p className="muted" style={{ fontSize: 13, fontWeight: 700 }}>{card.error ?? "Район недоступен."}</p>
          <button className="btn block" type="button" onClick={onClose}>Закрыть</button>
        </>
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
            {d.kind === "bot" && (
              <button className={`btn gold block ${!d.can_act || cd > 0 ? "off" : ""}`} type="button" disabled={busy || !d.can_act || cd > 0} onClick={online}>
                <Swords size={16} />Бой онлайн: перки и ходы
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
          {!event.won && bossCd <= 0 && <OnlineBattleButton path="/arena/start/boss" body={{ event_id: event.id }} label="Онлайн" disabled={busy} />}
        </div>
      </div>
    );
  }
  // Учитель техник / школы: «Взять задание» (как кнопка под учителем в боте), дальше — куда сдавать.
  const target = event.kind === "school" ? ROUTE_TRAINING : ROUTE_DEVELOPMENT;
  const where = event.kind === "school" ? "Тренировки" : "Развитие";
  const actions = (
    <>
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
    </>
  );
  // Есть портрет (assets/teacher_ut, assets/teacher_statist) — карточка как у босса.
  if (event.image) {
    return (
      <div className="boss-card teacher-card">
        <img src={imgUrl(event.image, 480)} alt={event.title} loading="lazy" />
        <div className="boss-over">
          <div className="boss-tag">{event.kind === "school" ? "УЧИТЕЛЬ СТАТИСТОВ" : "УЧИТЕЛЬ ТЕХНИКИ"}</div>
          <div className="disp" style={{ fontSize: 17, fontWeight: 800 }}>{event.title}</div>
          <div className="boss-desc">{event.subtitle} · исчезнет через {countdown(left)}</div>
          <div style={{ marginTop: "auto" }}>
            {event.state === "new" && (
              <button className="btn gold small teacher-btn" type="button" disabled={busy} onClick={() => onMeet(event)}>Взять задание</button>
            )}
            {event.state === "active" && (
              <Link className={`btn small teacher-btn ${event.quest_complete ? "green" : "ghost"}`} to={target}>
                {event.quest_complete ? "Сдать задание" : "Прогресс задания"}
              </Link>
            )}
            {event.state === "done" && (
              <Link className="btn ghost small teacher-btn" to={target}>{event.kind === "school" ? "Учитель открыт" : "Техника изучена"}</Link>
            )}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="tile">
      <div className="event-row">
        <div className="ico-box"><Users size={18} /></div>
        <div>
          <b>Учитель: {event.title}</b>
          <small style={{ display: "block" }}>{event.subtitle} · {countdown(left)}</small>
        </div>
      </div>
      {actions}
    </div>
  );
}

/** Круг: штурм ботов чужого города прямо из карточки на карте (онлайн-бой). */
function CityAssault({ cityId }: { cityId: number }) {
  const nav = useNavigate();
  const { run, busy } = useAction();
  return (
    <button type="button" className="btn red small" disabled={busy} onClick={async () => {
      const r = (await run("/arena/start/city", { city_id: cityId })) as { id?: string | null } | null;
      if (r?.id) nav(battlePath(r.id));
    }}><Swords size={14} />Штурм</button>
  );
}

function useWorld() {
  const [data, setData] = useState<WorldData | null>(null);
  const [geo, setGeo] = useState<Geo | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => apiGet<WorldData>("/map/world").then((d) => alive && setData(d)).catch(() => undefined);
    load();
    const t = setInterval(load, 10000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  useEffect(() => {
    if (!data?.geo || geo) return;
    fetch(`/geo/${data.geo}.json`).then((r) => r.json()).then(setGeo).catch(() => undefined);
  }, [data?.geo, geo]);
  return { data, geo };
}

export function MapPage() {
  const { data, status, error, reload } = useApi<MapData>("/map?page=0");
  const world = useWorld();
  const [cityId, setCityId] = useState<number | null>(null);
  const [selected, setSelected] = useState<MapDistrict | null>(null);
  const [foreign, setForeign] = useState<LiveDistrict | null>(null);
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
  const openDistrict = (d: LiveDistrict) =>
    setSelected({ id: d.id, number: d.number, kind: d.kind, owner: d.owner, bot_rank: null, bot_quantity: null, bot_power: d.bot_power ?? null });

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <RaidBanner />
          <ChallengesPanel />

          {world.data && world.geo ? (
            cityId !== null ? (
              <CityView cityId={cityId} myClan={world.data.my_clan} battles={world.data.battles}
                onBack={() => setCityId(null)} onDistrict={(d, own) => (own ? openDistrict(d) : setForeign(d))} />
            ) : (
              <WorldMap data={world.data} geo={world.geo} onOpenCity={(c) => setCityId(c.id)}
                extra={(c) => c.id === world.data?.my_city
                  ? <Link className="btn small" to={ROUTE_BUSINESS}><Building2 size={14} />Бизнесы</Link>
                  : world.data?.phase === PHASE_CIRCLE && c.bots > 0
                    ? <CityAssault cityId={c.id} />
                    : <Link className="btn ghost small" to={ROUTE_TRAVEL}><Luggage size={14} />Переезд</Link>} />
            )
          ) : (
            <div className="skeleton" style={{ height: 380, borderRadius: 14 }} />
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="stat-tile" style={{ textAlign: "left" }} onClick={() => world.data?.my_city && setCityId(world.data.my_city)}>
              <span className="muted">{data.city.name}</span><div className="disp" style={{ color: "var(--cyan)" }}>{data.my_districts} р-н.</div>
            </button>
            <div className="stat-tile"><span className="muted">Доход/мин</span><div className="disp" style={{ color: "var(--gold-2)" }}>+{fmt(Math.round(data.income_per_minute))}</div></div>
            <div className="stat-tile"><span className="muted">Атака через</span><div className="disp">{cd > 0 ? countdown(cd) : "готов"}</div></div>
          </div>
          {data.emperor && (
            <div className="map-emperor" style={{ alignSelf: "flex-start" }}><Crown size={14} />Император города: {data.emperor.name} · налог {data.emperor.tax_percent}%</div>
          )}

          {world.data && (
            <Panel title="ЛЕНТА СТРАНЫ">
              <EventFeed data={world.data} onCity={(id) => { setCityId(id); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
            </Panel>
          )}

          <div className="grid-4">
            <Link className="qa" to={ROUTE_GANG}><Users size={20} color="var(--cyan-2)" />Банда</Link>
            <Link className="qa" to={ROUTE_CARDS}><Layers size={20} color="var(--cyan-2)" />Уники</Link>
            <Link className="qa" to={`${ROUTE_GANG}#recruit`}><UserPlus size={20} color="var(--cyan-2)" />Вербовка</Link>
            <Link className="qa" to={ROUTE_BUSINESS}><Building2 size={20} color="var(--gold-2)" />Бизнес</Link>
          </div>
          {!data.can_attack && !data.empire && (
            <p className="muted" style={{ margin: 0, fontSize: 11, fontWeight: 700 }}>
              Твоя фаза воюет за город целиком — бои за города страны в разделе «Война за города».
            </p>
          )}

          <Link to={ROUTE_TRAVEL} className="emp-entry country">
            <span className="ico"><Luggage size={20} color="var(--cyan-2)" /></span>
            <span style={{ flex: 1, minWidth: 0 }}>
              <b>Переезд</b>
              <small>другой город или страна</small>
            </span>
            <ChevronRight size={18} />
          </Link>
          {(data.phase === PHASE_CIRCLE || data.phase === PHASE_FIST) && (
            <Link to={ROUTE_COUNTRY} className="emp-entry country">
              <span className="ico"><Flag size={20} color="var(--cyan-2)" /></span>
              <span style={{ flex: 1, minWidth: 0 }}>
                <b>Война за города</b>
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

      {foreign && (
        <Sheet title={`Район №${foreign.number}`} onClose={() => setForeign(null)}>
          <StatRow label="Владелец" value={foreign.kind === "bot" ? "боты" : foreign.owner ?? "—"} />
          <p className="muted" style={{ fontSize: 13, fontWeight: 700, margin: "10px 0" }}>
            {world.data?.phase === PHASE_CIRCLE
              ? "Круг берёт города целиком: штурмуй ботов этого города или брось вызов владельцам в «Войне за города»."
              : "Это чужой город — здесь можно только смотреть. Бои идут за районы твоего города: открой его и нажми на район ботов или игрока."}
          </p>
          {world.data?.phase === PHASE_CIRCLE && cityId !== null && (
            <OnlineBattleButton path="/arena/start/city" body={{ city_id: cityId }} label="Штурм ботов города онлайн" />
          )}
          {world.data?.phase === PHASE_CIRCLE && (
            <Link className="btn ghost block" style={{ marginTop: 8 }} to={ROUTE_COUNTRY}><Flag size={16} />Война за города</Link>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <button className="btn gold block" type="button" onClick={() => { setForeign(null); if (world.data?.my_city) setCityId(world.data.my_city); }}>
              <Swords size={16} />В мой город — к боям
            </button>
            <Link className="btn ghost block" to={ROUTE_TRAVEL}><Luggage size={16} />Переехать в этот город</Link>
          </div>
        </Sheet>
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
