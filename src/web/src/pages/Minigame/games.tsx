import { type ReactElement, useEffect, useRef, useState } from "react";

/** Параметры от сервера (`bot/config/minigame.params`). */
export type P = Record<string, number>;
export interface GameProps {
  p: P;
  onDone: (score: number) => void;
}

const rnd = (a: number, b: number) => a + Math.random() * (b - a);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function useAlive() {
  const alive = useRef(true);
  useEffect(() => () => void (alive.current = false), []);
  return alive;
}

function Hud({ left, right }: { left: string; right: string }) {
  return (
    <div className="mg-hud">
      <span>{left}</span>
      <span>{right}</span>
    </div>
  );
}

/** Точки: появляются в случайных местах и гаснут — успеть нажать. */
export function Dots({ p, onDone }: GameProps) {
  const [dot, setDot] = useState<{ id: number; x: number; y: number } | null>(null);
  const [hits, setHits] = useState(0);
  const [shown, setShown] = useState(0);
  const hitsRef = useRef(0);
  const alive = useAlive();
  useEffect(() => {
    (async () => {
      for (let i = 0; i < p.count; i++) {
        if (!alive.current) return;
        setDot({ id: i, x: rnd(8, 82), y: rnd(8, 82) });
        setShown(i + 1);
        await sleep(p.life_ms);
        setDot(null);
        await sleep(Math.max(80, p.gap_ms - p.life_ms / 2));
      }
      if (alive.current) onDone(hitsRef.current);
    })();
  }, []);
  return (
    <>
      <Hud left={`Попаданий ${hits}/${p.need}`} right={`${shown}/${p.count}`} />
      <div className="mg-area">
        {dot && (
          <button
            key={dot.id}
            className="mg-dot"
            style={{ left: `${dot.x}%`, top: `${dot.y}%` }}
            onPointerDown={() => {
              hitsRef.current += 1;
              setHits(hitsRef.current);
              setDot(null);
            }}
          />
        )}
      </div>
    </>
  );
}

/** Тайминг: бегунок ходит туда-сюда — нажать, когда он в зелёной зоне. */
export function Rhythm({ p, onDone }: GameProps) {
  const [round, setRound] = useState(0);
  const [hits, setHits] = useState(0);
  const [pos, setPos] = useState(0);
  const [zone, setZone] = useState(() => rnd(0.1, 0.9 - p.zone));
  const start = useRef(performance.now());
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const t = ((performance.now() - start.current) / 1000) * p.speed;
      setPos(1 - Math.abs((t % 2) - 1));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  const tap = () => {
    const ok = pos >= zone && pos <= zone + p.zone;
    const h = hits + (ok ? 1 : 0);
    setHits(h);
    if (round + 1 >= p.rounds) return onDone(h);
    setRound(round + 1);
    setZone(rnd(0.1, 0.9 - p.zone));
    start.current = performance.now() - rnd(0, 800);
  };
  return (
    <>
      <Hud left={`Попаданий ${hits}/${p.need}`} right={`${round + 1}/${p.rounds}`} />
      <div className="mg-area mg-tap" onPointerDown={tap}>
        <div className="mg-track">
          <div className="mg-zone" style={{ left: `${zone * 100}%`, width: `${p.zone * 100}%` }} />
          <div className="mg-marker" style={{ left: `${pos * 100}%` }} />
        </div>
        <small className="muted">Жми в любом месте, когда бегунок в зелёной зоне</small>
      </div>
    </>
  );
}

const ARROWS = ["↑", "→", "↓", "←"];

/** Комбо: запомнить показанную серию ударов и повторить. */
export function Combo({ p, onDone }: GameProps) {
  const [round, setRound] = useState(0);
  const [seq, setSeq] = useState<number[]>([]);
  const [lit, setLit] = useState<number | null>(null);
  const [input, setInput] = useState<number[]>([]);
  const [showing, setShowing] = useState(true);
  const [score, setScore] = useState(0);
  const alive = useAlive();
  const play = async (r: number) => {
    const s = Array.from({ length: p.length + r }, () => Math.floor(Math.random() * 4));
    setSeq(s);
    setInput([]);
    setShowing(true);
    await sleep(500);
    for (const k of s) {
      if (!alive.current) return;
      setLit(k);
      await sleep(p.show_ms);
      setLit(null);
      await sleep(150);
    }
    setShowing(false);
  };
  useEffect(() => void play(0), []);
  const next = (ok: boolean) => {
    const sc = score + (ok ? 1 : 0);
    setScore(sc);
    if (!ok || round + 1 >= p.rounds) return onDone(sc);
    setRound(round + 1);
    void play(round + 1);
  };
  const press = (k: number) => {
    if (showing) return;
    const inp = [...input, k];
    setInput(inp);
    if (seq[inp.length - 1] !== k) return next(false);
    if (inp.length === seq.length) next(true);
  };
  return (
    <>
      <Hud left={showing ? "Запоминай…" : `Повтори: ${input.length}/${seq.length}`} right={`Серия ${round + 1}/${p.rounds}`} />
      <div className="mg-area mg-combo">
        {ARROWS.map((a, i) => (
          <button key={a} className={`mg-key ${lit === i ? "lit" : ""}`} onPointerDown={() => press(i)}>
            {a}
          </button>
        ))}
      </div>
    </>
  );
}

/** Уклонение / блок: удар слева или справа — уйти в другую сторону. Выносливость мастерства: пропущенные
 * удары снимают мощь армии (полоса), армия должна выстоять. */
export function Dodge({ p, onDone }: GameProps) {
  const [side, setSide] = useState<0 | 1 | null>(null);
  const [n, setN] = useState(0);
  const [miss, setMiss] = useState(0);
  const missRef = useRef(0);
  const answered = useRef(true);
  const sideRef = useRef<0 | 1 | null>(null);
  const alive = useAlive();
  useEffect(() => {
    (async () => {
      await sleep(600);
      for (let i = 0; i < p.strikes; i++) {
        if (!alive.current) return;
        const s = Math.random() < 0.5 ? 0 : 1;
        sideRef.current = s;
        answered.current = false;
        setSide(s);
        setN(i + 1);
        await sleep(p.warn_ms);
        if (!answered.current) {
          missRef.current += 1;
          setMiss(missRef.current);
        }
        setSide(null);
        sideRef.current = null;
        await sleep(300);
      }
      if (alive.current) onDone(p.strikes - missRef.current);
    })();
  }, []);
  const tap = (s: 0 | 1) => {
    if (answered.current || sideRef.current === null) return;
    answered.current = true;
    if (s === sideRef.current) {
      missRef.current += 1; // ушёл под удар
      setMiss(missRef.current);
    }
    setSide(null);
  };
  const hp = p.army_power ? Math.max(0, p.army_power - miss * p.target_power * 0.12) / p.army_power : 1 - miss / (p.max_miss + 1);
  return (
    <>
      <Hud left={`Пропущено ${miss}/${p.max_miss}`} right={`${n}/${p.strikes}`} />
      <div className="mg-hp"><div style={{ width: `${hp * 100}%` }} /></div>
      <div className="mg-area mg-dodge">
        <button className={`mg-half ${side === 0 ? "danger" : ""}`} onPointerDown={() => tap(0)}>{side === 0 ? "👊" : ""}</button>
        <button className={`mg-half ${side === 1 ? "danger" : ""}`} onPointerDown={() => tap(1)}>{side === 1 ? "👊" : ""}</button>
      </div>
      <small className="muted">Удар с какой-то стороны — жми ПРОТИВОПОЛОЖНУЮ</small>
    </>
  );
}

/** Заряд: держи — шкала растёт, отпусти в зелёной полосе. */
export function Charge({ p, onDone }: GameProps) {
  const [round, setRound] = useState(0);
  const [hits, setHits] = useState(0);
  const [fill, setFill] = useState(0);
  const [band, setBand] = useState(() => rnd(0.45, 0.95 - p.band));
  const holding = useRef<number | null>(null);
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      if (holding.current !== null) setFill(((performance.now() - holding.current) / p.fill_ms) % 1.15);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  const release = () => {
    if (holding.current === null) return;
    holding.current = null;
    const ok = fill >= band && fill <= band + p.band;
    const h = hits + (ok ? 1 : 0);
    setHits(h);
    setFill(0);
    if (round + 1 >= p.rounds) return onDone(h);
    setRound(round + 1);
    setBand(rnd(0.45, 0.95 - p.band));
  };
  return (
    <>
      <Hud left={`Попаданий ${hits}/${p.need}`} right={`${round + 1}/${p.rounds}`} />
      <div className="mg-area mg-charge">
        <div className="mg-gauge">
          <div className="mg-band" style={{ bottom: `${band * 100}%`, height: `${p.band * 100}%` }} />
          <div className="mg-fill" style={{ height: `${Math.min(1, fill) * 100}%` }} />
        </div>
        <button
          className="btn red"
          onPointerDown={() => (holding.current = performance.now())}
          onPointerUp={release}
          onPointerLeave={release}
        >
          Держи и отпусти
        </button>
      </div>
    </>
  );
}

/** Шквал: набрать нужное число ударов за время. Сила мастерства: каждый удар — доля мощи армии. */
export function Mash({ p, onDone }: GameProps) {
  const [taps, setTaps] = useState(0);
  const [left, setLeft] = useState(p.seconds);
  const ref = useRef(0);
  useEffect(() => {
    const end = performance.now() + p.seconds * 1000;
    const t = setInterval(() => {
      const l = Math.max(0, (end - performance.now()) / 1000);
      setLeft(l);
      if (l <= 0) {
        clearInterval(t);
        onDone(ref.current);
      }
    }, 100);
    return () => clearInterval(t);
  }, []);
  const power = p.army_power ? Math.round((taps * p.army_power) / 40) : 0;
  return (
    <>
      <Hud
        left={p.army_power ? `Мощь ${power.toLocaleString("ru")} / ${p.target_power.toLocaleString("ru")}` : `Ударов ${taps}/${p.need}`}
        right={`${left.toFixed(1)} с`}
      />
      <div className="mg-area mg-tap mg-mash" onPointerDown={() => setTaps((ref.current += 1))}>
        <b>👊 {taps}</b>
        <small className="muted">Бей по экрану как можно быстрее</small>
      </div>
    </>
  );
}

/** Реакция: дождись сигнала и бей; раньше сигнала — фальстарт. */
export function Reaction({ p, onDone }: GameProps) {
  const [state, setState] = useState<"wait" | "go" | "early" | "late" | "hit">("wait");
  const [round, setRound] = useState(0);
  const [hits, setHits] = useState(0);
  const stateRef = useRef(state);
  const hitsRef = useRef(0);
  const alive = useAlive();
  const set = (s: typeof state) => {
    stateRef.current = s;
    setState(s);
  };
  useEffect(() => {
    (async () => {
      for (let r = 0; r < p.rounds; r++) {
        if (!alive.current) return;
        setRound(r);
        set("wait");
        await sleep(rnd(900, 2600));
        if (stateRef.current === "wait") {
          set("go");
          await sleep(p.window_ms);
          if ((stateRef.current as string) === "go") set("late");
        }
        await sleep(500);
      }
      if (alive.current) onDone(hitsRef.current);
    })();
  }, []);
  const tap = () => {
    if (stateRef.current === "wait") set("early");
    else if (stateRef.current === "go") {
      hitsRef.current += 1;
      setHits(hitsRef.current);
      set("hit");
    }
  };
  const label = { wait: "Жди…", go: "БЕЙ!", early: "Фальстарт", late: "Поздно", hit: "Есть!" }[state];
  return (
    <>
      <Hud left={`Попаданий ${hits}/${p.need}`} right={`${round + 1}/${p.rounds}`} />
      <div className={`mg-area mg-tap mg-react ${state}`} onPointerDown={tap}>
        <b>{label}</b>
      </div>
    </>
  );
}

/** Цель: движущаяся мишень отскакивает от краёв — попадай. */
export function Track({ p, onDone }: GameProps) {
  const [pos, setPos] = useState({ x: 0.5, y: 0.5 });
  const [hits, setHits] = useState(0);
  const [left, setLeft] = useState(p.seconds);
  const v = useRef({ x: p.speed * (Math.random() < 0.5 ? 1 : -1), y: p.speed * 0.8 });
  const ref = useRef(0);
  const done = useRef(false);
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const end = last + p.seconds * 1000;
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setPos((q) => {
        let { x, y } = q;
        x += v.current.x * dt;
        y += v.current.y * dt;
        if (x < 0 || x > 1 - p.size) v.current.x *= -1;
        if (y < 0 || y > 1 - p.size) v.current.y *= -1;
        return { x: Math.min(1 - p.size, Math.max(0, x)), y: Math.min(1 - p.size, Math.max(0, y)) };
      });
      setLeft(Math.max(0, (end - now) / 1000));
      if (now >= end) {
        if (!done.current) {
          done.current = true;
          onDone(ref.current);
        }
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  return (
    <>
      <Hud left={`Попаданий ${hits}/${p.need}`} right={`${left.toFixed(1)} с`} />
      <div className="mg-area">
        <button
          className="mg-target"
          style={{ left: `${pos.x * 100}%`, top: `${pos.y * 100}%`, width: `${p.size * 100}%`, height: `${p.size * 100}%` }}
          onPointerDown={() => {
            setHits((ref.current += 1));
            v.current = { x: -v.current.x * 1.05, y: v.current.y * 1.05 };
          }}
        />
      </div>
    </>
  );
}

export const GAMES: Record<string, { name: string; hint: string; C: (p: GameProps) => ReactElement }> = {
  dots: { name: "Точки", hint: "Жми на точки, пока не погасли", C: Dots },
  rhythm: { name: "Тайминг", hint: "Нажми, когда бегунок в зелёной зоне", C: Rhythm },
  combo: { name: "Комбо", hint: "Запомни серию ударов и повтори", C: Combo },
  dodge: { name: "Уклонение", hint: "Уходи от ударов в другую сторону", C: Dodge },
  charge: { name: "Заряд", hint: "Держи и отпусти в зелёной полосе", C: Charge },
  mash: { name: "Шквал", hint: "Бей как можно быстрее", C: Mash },
  reaction: { name: "Реакция", hint: "Дождись сигнала — и сразу бей", C: Reaction },
  track: { name: "Цель", hint: "Попадай по движущейся мишени", C: Track },
};
