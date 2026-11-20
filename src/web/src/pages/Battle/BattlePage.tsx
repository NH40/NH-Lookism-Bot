import { Bot, Shield, Swords, Users, Zap } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiGet, apiPost } from "../../api";
import { fmt, useToast } from "../../components/ui";
import { Sheet } from "../../components/Sheet";
import { ROUTE_MAP } from "../../constants";
import { gameOf, type P } from "../Minigame/games";
import "./Battle.css";

// Онлайн-бой (2026-11-19, экран переделан 2026-11-20): две карточки армий с силой, статистами и энергией,
// перки картами, живой журнал раундов (кто чем ходил, урон, павшие, сработавшие навыки), мини-игры поверх.
interface Perk { code: string; name: string; about: string; cost: number; ready_in: number; affordable: boolean; minigame?: string | null; game?: string | null }
interface Side {
  name: string; power: number; power0?: number; units?: number | null; units0?: number | null; energy: number; emax?: number;
  auto: boolean; afk?: boolean; waiting?: boolean; game?: { game: string; power: number } | null;
}
interface LogEntry {
  round: number; me: string; foe: string; me_name: string; foe_name: string; kills: number; lost: number;
  hit: number; taken: number; fired: string[]; foe_fired: string[];
}
interface BattleView {
  id: string; kind: string; status: "live" | "done"; round: number; left: number; me: Side; foe: Side; perks: Perk[];
  log: LogEntry[]; result: unknown; report: Record<string, unknown> | null; won: boolean | null;
}
type Pending = { perk?: string; enemy?: boolean; game: string; name?: string } | null;

const ROUND_SECONDS = 12;

/** Короткие параметры мини-игр в бою (3–5 с). */
function battleParams(game: string): P {
  const base: Record<string, P> = {
    rhythm: { rounds: 4, zone: 0.2, speed: 1.2, need: 3, max_score: 4, seconds: 4 },
    charge: { rounds: 3, band: 0.16, fill_ms: 1100, need: 2, max_score: 3, seconds: 3 },
    combo: { rounds: 1, length: 4, show_ms: 500, need: 1, max_score: 1, seconds: 3 },
    aim: { rounds: 3, size: 0.16, speed: 1.1, need: 2, max_score: 3, seconds: 4 },
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
};

function ArmyCard({ side, mine }: { side: Side; mine: boolean }) {
  const p0 = Math.max(1, side.power0 ?? side.power);
  const hp = Math.max(0, Math.min(1, side.power / p0));
  const emax = side.emax ?? 10;
  return (
    <div className={`bt-army ${mine ? "me" : "foe"}`}>
      <div className="bt-army-head">
        <span className="bt-ava">{mine ? "🥷" : "👊"}</span>
        <div className="bt-army-name">
          <b>{side.name}</b>
          <small>{side.afk ? (mine ? "🤖 ты пропустил ходы — включена автоатака" : "🤖 соперник не ходит — за него автоатака") : side.auto ? "🤖 автоатака" : side.waiting ? "✅ ход сделан" : mine ? "👤 твой ход" : "🤔 думает…"}</small>
        </div>
        <span className="bt-pow">{fmt(side.power)}</span>
      </div>
      <div className="bt-hp"><i style={{ width: `${hp * 100}%` }} /></div>
      <div className="bt-army-row">
        <span><Users size={12} /> {side.units != null ? `${fmt(side.units)}${side.units0 ? ` / ${fmt(side.units0)}` : ""}` : "—"}</span>
        <span className="bt-pips" title="энергия">
          {Array.from({ length: emax }, (_, i) => <i key={i} className={i < side.energy ? "on" : ""} />)}
          <small><Zap size={11} />{side.energy}</small>
        </span>
      </div>
    </div>
  );
}

function RoundLine({ e }: { e: LogEntry }) {
  return (
    <div className="bt-round">
      <div className="bt-round-n">Р{e.round}</div>
      <div className="bt-round-body">
        <div className="bt-line me">
          <b>Ты: {e.me_name}</b>
          <span>💥 {fmt(e.hit)} урона · ☠️ пало врагов {fmt(e.kills)}</span>
          {e.fired.length > 0 && <div className="bt-tags">{e.fired.map((f) => <i key={f}>{f}</i>)}</div>}
        </div>
        <div className="bt-line foe">
          <b>Враг: {e.foe_name}</b>
          <span>💥 {fmt(e.taken)} урона · ☠️ пало твоих {fmt(e.lost)}</span>
          {e.foe_fired.length > 0 && <div className="bt-tags">{e.foe_fired.map((f) => <i key={f}>{f}</i>)}</div>}
        </div>
      </div>
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
    if (game.enemy) send("act", { kind: "attack", game_score: ratio });
    else act("perk", { perk: game.perk, score: ratio });
    setGame(null);
  };

  if (!b) return <div className="page"><div className="skeleton" style={{ height: 300 }} /></div>;
  const G = game ? gameOf(game.game) : null;
  const live = b.status === "live";
  const canAct = live && !busy && !b.me.waiting && !b.me.auto;
  return (
    <div className="page bt">
      <div className="bt-top">
        <div>
          <b>{KIND_TITLE[b.kind] ?? "Бой"}</b>
          <small>Раунд {b.round + (live ? 1 : 0)}</small>
        </div>
        {live && (
          <div className={`bt-timer ${left <= 3 ? "hot" : ""}`} style={{ ["--p" as string]: `${(left / ROUND_SECONDS) * 100}%` }}>
            <span>{left}</span>
          </div>
        )}
        <button type="button" className={`btn small ${b.me.auto ? "gold" : "ghost"}`} disabled={!live || busy}
          onClick={() => send("auto", { on: !b.me.auto })}><Bot size={14} /> {b.me.auto ? "Авто: вкл" : "Авто-бой"}</button>
      </div>

      <ArmyCard side={b.foe} mine={false} />
      <div className={`bt-clash ${flash ? "go" : ""}`}>
        {flash ? (
          <span>💥 {fmt(flash.hit)} → · ← {fmt(flash.taken)} 💥</span>
        ) : (
          <span><Swords size={18} /> {live ? (b.me.waiting ? "Ждём ход соперника…" : b.me.auto ? "Ходит автоатака" : "Выбери ход") : "Бой окончен"}</span>
        )}
      </div>
      <ArmyCard side={b.me} mine />

      {live ? (
        <>
          <div className="grid-2" style={{ gap: 8 }}>
            <button type="button" className="btn red bt-big" disabled={!canAct} onClick={() => act("attack")}><Swords size={18} /> Атака</button>
            <button type="button" className="btn ghost bt-big" disabled={!canAct} onClick={() => act("defend")}><Shield size={18} /> Защита <small>+⚡</small></button>
          </div>
          {b.me.auto && <small className="muted bt-note">Автоатака ходит за тебя. Выключи «Авто-бой», чтобы играть перками сам.</small>}
          {b.perks.length > 0 && (
            <>
              <div className="bt-sub">Способности <small>🎮 мини-игра для тебя · 🎯 испытание сопернику</small></div>
              <div className="bt-plist">
                {b.perks.map((p) => {
                  const ok = canAct && p.ready_in === 0 && p.affordable;
                  return (
                    <button key={p.code} type="button" className={`bt-prow ${ok ? "" : "off"} ${p.minigame ? `mg-${p.minigame}` : ""}`}
                      onClick={() => setInfo(p)}>
                      <span className="bt-prow-ico">{p.minigame === "self" ? "🎮" : p.minigame === "enemy" ? "🎯" : "✦"}</span>
                      <b>{p.name}</b>
                      <span className="bt-prow-meta">
                        {p.ready_in > 0 ? `⏳ ${p.ready_in}` : !p.affordable ? "мало ⚡" : ""}
                        <i><Zap size={11} />{p.cost}</i>
                      </span>
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

      {b.log.length > 0 && (
        <>
          <div className="bt-sub">Ход боя</div>
          <div className="bt-log">{[...b.log].reverse().map((e) => <RoundLine key={e.round} e={e} />)}</div>
        </>
      )}

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
