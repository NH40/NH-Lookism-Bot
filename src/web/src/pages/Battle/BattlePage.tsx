import { Bot, ChevronRight, Shield, Swords, Users, Zap } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiGet, apiPost, imgUrl } from "../../api";
import { Sheet } from "../../components/Sheet";
import { ArenaPerksSheet } from "../../components/ArenaPerksSheet";
import { fmt, useToast } from "../../components/ui";
import { ROUTE_MAP } from "../../constants";
import { gameOf, type P } from "../Minigame/games";
import "./Battle.css";

// Онлайн-бой (2026-11-19; дизайн 2026-11-20): «ты против соперника» с портретами (уник-лидер банды),
// мощью, статистами и энергией; аккуратный список перков с окном описания; живая лента раундов.
interface Perk { code: string; name: string; about: string; cost: number; ready_in: number; affordable: boolean; minigame?: string | null; game?: string | null }
interface Side {
  name: string; power: number; power0?: number; units?: number | null; units0?: number | null; energy: number; emax?: number;
  auto: boolean; afk?: boolean; waiting?: boolean; chosen?: string | null; ava?: string | null; bot?: boolean;
  game?: { game: string; power: number } | null;
}
interface LogEntry {
  round: number; me: string; foe: string; me_name: string; foe_name: string; kills: number; lost: number;
  hit: number; taken: number; fired: string[]; foe_fired: string[];
  /** Разбор раунда «откуда что» — готовые строки с сервера (`services/combat/explain`). */
  lines?: string[]; foe_lines?: string[];
}
interface BattleView {
  id: string; kind: string; status: "live" | "done"; round: number; left: number; me: Side; foe: Side; perks: Perk[];
  log: LogEntry[]; result: unknown; report: Record<string, unknown> | null; won: boolean | null;
  /** Влияние мощи: перевес и сколько прокачки слабого работает. */
  power_line?: string | null;
}

const LOG_MODE_KEY = "lbp.battle.logMode"; // «кратко / подробно» — удобство одного зрителя, не игровое состояние
function readLogMode(): boolean {
  try {
    return localStorage.getItem(LOG_MODE_KEY) === "full";
  } catch {
    return false;
  }
}
function saveLogMode(full: boolean) {
  try {
    localStorage.setItem(LOG_MODE_KEY, full ? "full" : "short");
  } catch {
    /* приватный режим — просто не запоминаем */
  }
}

function Lines({ lines }: { lines?: string[] }) {
  if (!lines?.length) return null;
  return <div className="bt-why">{lines.map((l, i) => <div key={i} className={l.startsWith("  ") ? "sub" : ""}>{l.trim()}</div>)}</div>;
}
type Pending = { perk?: string; enemy?: boolean; game: string; name?: string } | null;

const ROUND_SECONDS = 30;

/** Короткие параметры мини-игр в бою (3–5 с). */
function battleParams(game: string): P {
  const base: Record<string, P> = {
    rhythm: { rounds: 4, zone: 0.2, speed: 1.2, need: 3, max_score: 4, seconds: 4 },
    charge: { rounds: 3, band: 0.16, fill_ms: 1100, need: 2, max_score: 3, seconds: 3 },
    combo: { rounds: 1, length: 4, show_ms: 500, need: 1, max_score: 1, seconds: 3 },
    aim: { rounds: 3, size: 0.16, speed: 0.6, need: 2, max_score: 3, seconds: 4 }, // мишень проходится за ~130 мс, а не 70
    reaction: { rounds: 3, window_ms: 480, need: 2, max_score: 3, seconds: 4 },
    dodge: { strikes: 6, warn_ms: 650, max_miss: 2, need: 4, max_score: 6, seconds: 5 },
    gonogo: { rounds: 6, window_ms: 700, decoy: 0.4, need: 4, max_score: 6, seconds: 5 },
    parry: { strikes: 5, warn_ms: 800, need: 3, max_score: 5, seconds: 5 },
    arrows: { rounds: 5, window_ms: 900, need: 3, max_score: 5, seconds: 5 },
  };
  return base[game] ?? base.reaction;
}

const KIND_TITLE: Record<string, string> = {
  district: "Бой за район", challenge: "Вызов", boss: "Босс", city: "Штурм города", raid: "Рейд", war: "Война вождей",
  tom: "Том Ли", throne: "Бой за трон", liberation: "Освобождение страны", clan_war: "Клановая война", tutorial: "Обучение",
};
const BOT_FACE: Record<string, string> = { boss: "👹", raid: "🏴‍☠️", district: "🤖", city: "🏯", tom: "🥋", clan_war: "🏰", tutorial: "🎓" };

function status(side: Side, mine: boolean): string {
  if (side.afk) return mine ? "пропустил ходы · автоатака" : "не ходит · автоатака";
  if (side.auto) return "🤖 автоатака";
  if (side.waiting) return mine ? `✅ ${side.chosen ?? "ход сделан"}` : "✅ сходил";
  return mine ? "твой ход" : "думает…";
}

function Fighter({ side, mine, kind }: { side: Side; mine: boolean; kind: string }) {
  const p0 = Math.max(1, side.power0 ?? side.power);
  const hp = Math.max(0, Math.min(1, side.power / p0));
  const emax = side.emax ?? 10;
  const initial = side.name.replace(/[^\p{L}\p{N}]/gu, "").slice(0, 1).toUpperCase() || "?";
  return (
    <div className={`bt-f ${mine ? "me" : "foe"}`}>
      <div className="bt-f-ava">
        {side.ava ? <img src={imgUrl(side.ava, 160)} alt={side.name} /> : <span>{side.bot ? BOT_FACE[kind] ?? "🤖" : initial}</span>}
        <i className={`bt-f-dot ${side.waiting || side.auto ? "ok" : ""}`} />
      </div>
      <b className="bt-f-name">{side.name}</b>
      <small className="bt-f-status">{status(side, mine)}</small>
      <div className="bt-f-pow">{fmt(side.power)}</div>
      <div className="bt-hp"><i style={{ width: `${hp * 100}%` }} /></div>
      <div className="bt-f-row">
        <span><Users size={11} /> {side.units != null ? fmt(side.units) : "—"}</span>
        <span className="bt-en"><Zap size={11} /> {side.energy}/{emax}</span>
      </div>
      <div className="bt-pips">{Array.from({ length: emax }, (_, i) => <i key={i} className={i < side.energy ? "on" : ""} />)}</div>
    </div>
  );
}

function RoundCard({ e, fresh, full }: { e: LogEntry; fresh: boolean; full: boolean }) {
  const won = e.kills >= e.lost;
  const [open, setOpen] = useState(full);
  useEffect(() => setOpen(full), [full]);
  const has = !!(e.lines?.length || e.foe_lines?.length);
  return (
    <div className={`bt-rc ${fresh ? "fresh" : ""}`}>
      <div className="bt-rc-head">
        <b>Раунд {e.round}</b>
        <span className={won ? "up" : "down"}>{won ? "▲ за тобой" : "▼ за соперником"}</span>
      </div>
      <div className="bt-rc-side me">
        <span className="bt-rc-who">Ты</span>
        <div>
          <b>{e.me_name}</b>
          <small>💥 {fmt(e.hit)} · ☠️ −{fmt(e.kills)} у врага</small>
          {e.fired.length > 0 && <div className="bt-tags">{e.fired.map((f) => <i key={f}>{f}</i>)}</div>}
          {open && <Lines lines={e.lines} />}
        </div>
      </div>
      <div className="bt-rc-side foe">
        <span className="bt-rc-who">Враг</span>
        <div>
          <b>{e.foe_name}</b>
          <small>💥 {fmt(e.taken)} · ☠️ −{fmt(e.lost)} у тебя</small>
          {e.foe_fired.length > 0 && <div className="bt-tags">{e.foe_fired.map((f) => <i key={f}>{f}</i>)}</div>}
          {open && <Lines lines={e.foe_lines} />}
        </div>
      </div>
      {has && (
        <button type="button" className="bt-why-btn" onClick={() => setOpen(!open)}>
          {open ? "Свернуть разбор" : "🔎 Почему столько? Разбор раунда"}
        </button>
      )}
    </div>
  );
}

export function BattlePage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [b, setB] = useState<BattleView | null>(null);
  const [left, setLeft] = useState(0);
  const [busy, setBusy] = useState(false);
  const [game, setGame] = useState<Pending>(null);
  const [flash, setFlash] = useState<LogEntry | null>(null);
  const [info, setInfo] = useState<Perk | null>(null);
  const [perksOpen, setPerksOpen] = useState(false);
  const [fullLog, setFullLog] = useState(readLogMode);
  const lastRound = useRef(0);

  const apply = useCallback((v: BattleView) => {
    setB(v);
    setLeft(v.left);
    const last = v.log[v.log.length - 1];
    if (last && last.round > lastRound.current) {
      if (lastRound.current) setFlash(last);
      lastRound.current = last.round;
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const v = await apiGet<BattleView>(`/arena/${id}`);
      apply(v);
      if (v.me.game && !game && !v.me.auto) setGame({ enemy: true, game: v.me.game.game });
    } catch (e) {
      toast(String((e as Error).message || e));
    }
  }, [id, game, apply]);

  useEffect(() => {
    load();
    const t = setInterval(() => b?.status !== "done" && load(), 1500);
    const s = setInterval(() => setLeft((x) => Math.max(0, x - 1)), 1000);
    return () => { clearInterval(t); clearInterval(s); };
  }, [id, b?.status]);

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(null), 2600);
    return () => clearTimeout(t);
  }, [flash]);

  const send = async (path: string, body: object) => {
    if (busy) return;
    setBusy(true);
    try {
      apply(await apiPost<BattleView>(`/arena/${id}/${path}`, body));
    } catch (e) {
      toast(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  };
  const act = (kind: string, extra: object = {}) => send("act", { kind, ...extra });
  const usePerk = (p: Perk) => {
    if (p.minigame === "self" && p.game) setGame({ perk: p.code, game: p.game, name: p.name });
    else act("perk", { perk: p.code });
  };
  const gameDone = (score: number) => {
    if (!game) return;
    const p = battleParams(game.game);
    const ratio = Math.max(0, Math.min(1, score / (p.max_score || 1)));
    if (game.enemy) send("act", { kind: "game", game_score: ratio }); // только результат испытания — ход выбираешь сам
    else act("perk", { perk: game.perk, score: ratio });
    setGame(null);
  };

  if (!b) return <div className="page"><div className="skeleton" style={{ height: 300 }} /></div>;
  const G = game ? gameOf(game.game) : null;
  const live = b.status === "live";
  const canAct = live && !busy && !b.me.waiting && !b.me.auto;
  const lastLog = b.log[b.log.length - 1];
  return (
    <div className="page bt">
      <div className="bt-top">
        <div className="bt-title">
          <b>{KIND_TITLE[b.kind] ?? "Бой"}</b>
          <small>{live ? `Раунд ${b.round + 1}` : `Сыграно раундов: ${b.round}`}</small>
        </div>
        <button type="button" className="bt-auto" onClick={() => setPerksOpen(true)} aria-label="Способности">⚙</button>
        <button type="button" className={`bt-auto ${b.me.auto ? "on" : ""}`} disabled={!live || busy}
          onClick={() => send("auto", { on: !b.me.auto })}>
          <Bot size={15} /> {b.me.auto ? "Авто: вкл" : "Авто-бой"}
        </button>
        {live && b.foe.auto && (
          <button type="button" className="bt-auto" disabled={busy} onClick={() => send("finish", {})} title="Соперник на автобое — доиграть сразу">
            ⏩ Досчитать
          </button>
        )}
      </div>
      {b.power_line && <div className="bt-power">{b.power_line}</div>}

      <div className="bt-vs">
        <Fighter side={b.me} mine kind={b.kind} />
        <div className="bt-vs-mid">
          {live ? (
            <div className={`bt-timer ${left <= 3 ? "hot" : ""}`} style={{ ["--p" as string]: `${(left / ROUND_SECONDS) * 100}%` }}>
              <span>{left}</span>
            </div>
          ) : <div className="bt-vs-badge">VS</div>}
          {flash ? (
            <div className="bt-hits">
              <span className="me">−{fmt(flash.kills)}</span>
              <span className="foe">−{fmt(flash.lost)}</span>
            </div>
          ) : <div className="bt-vs-badge small">VS</div>}
        </div>
        <Fighter side={b.foe} mine={false} kind={b.kind} />
      </div>

      {live ? (
        <>
          {b.me.afk && b.me.auto && (
            <button type="button" className="bt-afk" disabled={busy} onClick={() => send("auto", { on: false })}>
              🤖 Ты пропустил ходы — включилась автоатака. <b>Играть самому</b>
            </button>
          )}
          <div className={`bt-turn ${canAct ? "go" : ""}`}>
            {b.me.auto ? "Ходит автоатака — выключи «Авто-бой», чтобы играть самому"
              : b.me.waiting ? `Ход сделан: ${b.me.chosen ?? "—"} · ждём соперника`
                : "Твой ход — атака, защита или способность"}
          </div>
          <div className="bt-actions">
            <button type="button" className="bt-act atk" disabled={!canAct} onClick={() => act("attack")}><Swords size={20} /><b>Атака</b><small>обычный удар</small></button>
            <button type="button" className="bt-act def" disabled={!canAct} onClick={() => act("defend")}><Shield size={20} /><b>Защита</b><small>меньше урона · +⚡</small></button>
          </div>
          {b.perks.length > 0 && (
            <>
              <div className="bt-sub">Способности <small>{b.perks.filter((p) => p.ready_in === 0 && p.affordable).length} из {b.perks.length} готовы</small></div>
              <div className="bt-plist">
                {b.perks.map((p) => {
                  const ok = canAct && p.ready_in === 0 && p.affordable;
                  const tag = p.ready_in > 0 ? `⏳ ${p.ready_in} р.` : !p.affordable ? "мало ⚡" : null;
                  return (
                    <button key={p.code} type="button" className={`bt-prow ${ok ? "ready" : "off"} ${p.minigame ? `mg-${p.minigame}` : ""}`} onClick={() => setInfo(p)}>
                      <span className="bt-prow-ico">{p.minigame === "self" ? "🎮" : p.minigame === "enemy" ? "🎯" : "✦"}</span>
                      <span className="bt-prow-txt"><b>{p.name}</b><small>{p.about}</small></span>
                      {tag ? <span className="bt-prow-tag">{tag}</span> : <span className="bt-prow-cost"><Zap size={11} />{p.cost}</span>}
                      <ChevronRight size={14} className="bt-prow-go" />
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </>
      ) : (
        <div className={`bt-result ${b.won ? "win" : "lose"}`}>
          <b>{b.won ? "🏆 Победа!" : "💀 Поражение"}</b>
          {b.report && "captured" in b.report && <span>{b.report.captured ? "Район захвачен" : "Район не взят"}</span>}
          <button type="button" className="btn block" style={{ marginTop: 10 }} onClick={() => nav(ROUTE_MAP)}>На карту</button>
        </div>
      )}

      <div className="bt-sub">Лента боя <small>{live ? "обновляется вживую" : "итог"}</small></div>
      <div className="bt-feed">
        {live && (
          <div className="bt-now">
            <span className="bt-live">LIVE</span>
            <span>Раунд {b.round + 1}: ты — <b>{b.me.waiting || b.me.auto ? (b.me.chosen ?? (b.me.auto ? "автоатака" : "выбрал")) : "выбираешь…"}</b>
              {" · "}соперник — <b>{b.foe.waiting ? "сходил" : b.foe.auto ? "автоатака" : "думает…"}</b></span>
          </div>
        )}
        {b.log.length > 0 && (
          <div className="bt-logmode">
            <span>Лог боя</span>
            <button type="button" className={!fullLog ? "on" : ""} onClick={() => { setFullLog(false); saveLogMode(false); }}>кратко</button>
            <button type="button" className={fullLog ? "on" : ""} onClick={() => { setFullLog(true); saveLogMode(true); }}>подробно</button>
          </div>
        )}
        {[...b.log].reverse().map((e) => <RoundCard key={e.round} e={e} full={fullLog} fresh={e.round === lastLog?.round && !!flash} />)}
        {!b.log.length && !live && <small className="muted">Раундов не было.</small>}
      </div>

      {info && (() => {
        const p = b.perks.find((x) => x.code === info.code) ?? info;
        const ok = canAct && p.ready_in === 0 && p.affordable;
        return (
          <Sheet title={p.name} onClose={() => setInfo(null)}>
            <div className="bt-pinfo">
              <p>{p.about}</p>
              <div className="bt-pinfo-chips">
                <span><Zap size={12} /> {p.cost} энергии (у тебя {b.me.energy})</span>
                {p.ready_in > 0 && <span>⏳ готов через {p.ready_in} р.</span>}
                {p.minigame === "self" && <span>🎮 мини-игра: сыграешь лучше — удар сильнее</span>}
                {p.minigame === "enemy" && <span>🎯 сопернику — испытание, провал = больше урона</span>}
              </div>
              <button type="button" className="btn gold block" disabled={!ok} onClick={() => { setInfo(null); usePerk(p); }}>
                {ok ? "Использовать" : b.me.auto ? "Выключи автобой, чтобы ходить самому" : b.me.waiting ? "Ход уже сделан" : p.ready_in > 0 ? "Перезаряжается" : !p.affordable ? "Не хватает энергии" : "Сейчас нельзя"}
              </button>
            </div>
          </Sheet>
        );
      })()}

      {perksOpen && <ArenaPerksSheet onClose={() => setPerksOpen(false)} />}

      {G && game && (
        <div className="bt-game">
          <div className={`bt-game-box ${game.enemy ? "enemy" : ""}`}>
            <b>{game.enemy ? "🎯 Соперник навязал испытание!" : `🎮 ${game.name ?? "Мини-игра перка"}`}</b>
            <small className="muted">{game.enemy ? "Сыграй хорошо — иначе получишь больше урона. " : "Чем лучше сыграешь, тем сильнее удар. "}{G.hint}</small>
            <G.C p={battleParams(game.game)} onDone={gameDone} />
          </div>
        </div>
      )}
    </div>
  );
}
