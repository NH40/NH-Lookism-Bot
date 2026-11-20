import { Bot, Shield, Swords, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiGet, apiPost } from "../../api";
import { fmt, useToast } from "../../components/ui";
import { ROUTE_MAP } from "../../constants";
import { gameOf, type P } from "../Minigame/games";
import "./Battle.css";

// Онлайн-бой (2026-11-19): раунды по 12 с — атака, защита или перк; автоатака; мини-игры сильных перков.
interface Perk { code: string; name: string; about: string; cost: number; ready_in: number; affordable: boolean; minigame?: string | null; game?: string | null }
interface Side { name: string; power: number; energy: number; emax?: number; auto: boolean; waiting?: boolean; game?: { game: string; power: number } | null }
interface BattleView {
  id: string; kind: string; status: "live" | "done"; round: number; left: number; me: Side; foe: Side; perks: Perk[];
  log: { me: string; foe: string; kills: number; lost: number }[]; result: unknown; report: Record<string, unknown> | null; won: boolean | null;
}
type Pending = { perk?: string; enemy?: boolean; game: string } | null;

const ACTION_NAMES: Record<string, string> = { attack: "Атака", defend: "Защита" };

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

export function BattlePage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [b, setB] = useState<BattleView | null>(null);
  const [left, setLeft] = useState(0);
  const [busy, setBusy] = useState(false);
  const [game, setGame] = useState<Pending>(null);

  const load = useCallback(async () => {
    try {
      const v = await apiGet<BattleView>(`/arena/${id}`);
      setB(v);
      setLeft(v.left);
      if (v.me.game && !game) setGame({ enemy: true, game: v.me.game.game });
    } catch (e) {
      toast(String((e as Error).message || e));
    }
  }, [id, game]);

  useEffect(() => {
    load();
    const t = setInterval(() => b?.status !== "done" && load(), 1500);
    const s = setInterval(() => setLeft((x) => Math.max(0, x - 1)), 1000);
    return () => { clearInterval(t); clearInterval(s); };
  }, [id, b?.status]);

  const send = async (path: string, body: object) => {
    if (busy) return;
    setBusy(true);
    try {
      setB(await apiPost<BattleView>(`/arena/${id}/${path}`, body));
    } catch (e) {
      toast(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  };
  const act = (kind: string, extra: object = {}) => send("act", { kind, ...extra });
  const usePerk = (p: Perk) => {
    if (p.minigame === "self" && p.game) setGame({ perk: p.code, game: p.game });
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
  const meShare = b.me.power / Math.max(1, b.me.power + b.foe.power);
  return (
    <div className="page bt">
      <div className="bt-top">
        <span>Раунд {b.round + (b.status === "live" ? 1 : 0)}</span>
        <b className={left <= 3 ? "bt-red" : ""}>{b.status === "live" ? `${left} с` : "Бой окончен"}</b>
        <button type="button" className={`btn small ${b.me.auto ? "gold" : "ghost"}`} disabled={b.status !== "live" || busy}
          onClick={() => send("auto", { on: !b.me.auto })}><Bot size={14} /> {b.me.auto ? "Авто: вкл" : "Авто"}</button>
      </div>
      <div className="bt-board">
        <div className="bt-card foe">
          <b>{b.foe.name}</b>
          <span>мощь {fmt(b.foe.power)}</span>
          <small>{b.foe.auto ? "🤖 автоатака" : "👤 играет сам"} · ⚡ {b.foe.energy}</small>
        </div>
        <div className="bt-clash"><div className="bt-bar"><i style={{ width: `${meShare * 100}%` }} /></div><Swords size={22} /></div>
        <div className="bt-card me">
          <b>{b.me.name}</b>
          <span>мощь {fmt(b.me.power)}</span>
          <small>⚡ {b.me.energy}/{b.me.emax ?? 10}{b.me.waiting ? " · ход сделан, ждём соперника" : ""}</small>
        </div>
      </div>
      {b.status === "live" ? (
        <>
          <div className="grid-2" style={{ gap: 8 }}>
            <button type="button" className="btn red" disabled={busy || b.me.waiting || b.me.auto} onClick={() => act("attack")}><Swords size={16} /> Атака</button>
            <button type="button" className="btn ghost" disabled={busy || b.me.waiting || b.me.auto} onClick={() => act("defend")}><Shield size={16} /> Защита</button>
          </div>
          {b.perks.some((p) => p.minigame) && (
            <small className="muted" style={{ fontSize: 11, fontWeight: 700 }}>🎮 — мини-игра для тебя (сыграешь лучше — сильнее удар) · 🎯 — навязать испытание сопернику</small>
          )}
          <div className="bt-perks">
            {b.perks.map((p) => {
              const ok = p.ready_in === 0 && p.affordable && !b.me.waiting && !b.me.auto;
              return (
                <button key={p.code} type="button" className={`bt-perk ${ok ? "" : "off"}`} disabled={busy || !ok} title={p.about} onClick={() => usePerk(p)}>
                  <b>{p.minigame === "self" ? "🎮 " : p.minigame === "enemy" ? "🎯 " : ""}{p.name}</b>
                  <small><Zap size={11} />{p.cost}{p.ready_in ? ` · через ${p.ready_in}` : ""}</small>
                </button>
              );
            })}
          </div>
        </>
      ) : (
        <div className={`bt-result ${b.won ? "win" : "lose"}`}>
          <b>{b.won ? "Победа!" : "Поражение"}</b>
          {b.report && "captured" in b.report && <span>{b.report.captured ? "Район захвачен" : "Район не взят"}</span>}
          <button type="button" className="btn block" style={{ marginTop: 10 }} onClick={() => nav(ROUTE_MAP)}>На карту</button>
        </div>
      )}
      <div className="bt-log">
        {[...b.log].reverse().map((e, i) => (
          <div key={i}><span>{ACTION_NAMES[e.me] ?? perkName(b.perks, e.me)}</span><span className="muted">vs {ACTION_NAMES[e.foe] ?? "перк"}</span><span>−{fmt(e.lost)} / +{fmt(e.kills)}</span></div>
        ))}
      </div>
      {G && game && (
        <div className="bt-game">
          <div className="bt-game-box">
            <b>{game.enemy ? "Противник навязал испытание!" : "Мини-игра перка"}</b>
            <small className="muted">{G.hint}</small>
            <G.C p={battleParams(game.game)} onDone={gameDone} />
          </div>
        </div>
      )}
    </div>
  );
}

function perkName(perks: Perk[], code: string) {
  return perks.find((p) => p.code === code)?.name ?? "Перк";
}
