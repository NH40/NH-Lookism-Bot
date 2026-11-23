import { type ReactElement, useEffect, useRef, useState } from "react";
import type { GameProps } from "./games";

// 13 механик (2026-11-19): вместе с 8 из games.tsx — 21; у каждой одна версия (2026-11-23).
const rnd = (a: number, b: number) => a + Math.random() * (b - a);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const ARROWS = ["⬆️", "⬇️", "⬅️", "➡️"];
const STANCES = ["🥋", "🦵", "👊", "🛡️", "🤺", "🐍"];

function useAlive() {
  const alive = useRef(true);
  useEffect(() => () => void (alive.current = false), []);
  return alive;
}

function Hud({ left, right }: { left: string; right: string }) {
  return <div className="mg-hud"><span>{left}</span><span>{right}</span></div>;
}

/** Ждать ответа игрока не дольше `ms`: → индекс ответа или null. */
function useAnswer() {
  const res = useRef<((v: number | null) => void) | null>(null);
  const ask = (ms: number) => new Promise<number | null>((r) => {
    res.current = r;
    setTimeout(() => { if (res.current === r) { res.current = null; r(null); } }, ms);
  });
  const answer = (v: number) => { const r = res.current; res.current = null; r?.(v); };
  return { ask, answer };
}

function useTimer(seconds: number, onEnd: () => void) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    const end = performance.now() + seconds * 1000;
    const t = setInterval(() => {
      const l = Math.max(0, (end - performance.now()) / 1000);
      setLeft(l);
      if (l <= 0) { clearInterval(t); onEnd(); }
    }, 100);
    return () => clearInterval(t);
  }, []);
  return left;
}

/** N точек без наложения (раньше кружки могли лечь друг на друга — нажимался не тот). */
function spread(n: number): [number, number][] {
  const out: [number, number][] = [];
  for (let tries = 0; out.length < n && tries < 400; tries++) {
    const x = rnd(6, 84), y = rnd(6, 84);
    if (out.every(([a, b]) => Math.hypot(a - x, b - y) > 18)) out.push([x, y]);
  }
  while (out.length < n) out.push([rnd(6, 84), rnd(6, 84)]);
  return out;
}

/** Порядок: нажми кружки 1…N по порядку. */
export function Order({ p, onDone }: GameProps) {
  const [dots, setDots] = useState<{ n: number; x: number; y: number }[]>([]);
  const [score, setScore] = useState(0);
  const [round, setRound] = useState(0);
  const next = useRef(1);
  const { ask, answer } = useAnswer();
  const alive = useAlive();
  useEffect(() => {
    (async () => {
      let s = 0;
      for (let r = 0; r < p.rounds; r++) {
        if (!alive.current) return;
        setRound(r + 1);
        next.current = 1;
        setDots(spread(p.length).map(([x, y], i) => ({ n: i + 1, x, y })));
        const ok = await ask(p.round_ms);
        if (ok === 1) setScore(++s);
        setDots([]);
        await sleep(250);
      }
      if (alive.current) onDone(s);
    })();
  }, []);
  return (
    <>
      <Hud left={`Раундов ${score}/${p.need}`} right={`${round}/${p.rounds}`} />
      <div className="mg-area">
        {dots.map((d) => (
          <button key={d.n} className="mg-dot mg-num" style={{ left: `${d.x}%`, top: `${d.y}%` }} onPointerDown={() => {
            if (d.n !== next.current) return answer(0);
            setDots((xs) => xs.filter((x) => x.n !== d.n));
            next.current += 1;
            if (next.current > p.length) answer(1);
          }}>{d.n}</button>
        ))}
      </div>
    </>
  );
}

/** Выбор из вариантов под таймер: стрелки, стойки, парирование. */
function Choice({ p, onDone, total, options, show, hint, fixed }: GameProps & { total: number; options: string[]; show: (i: number) => string; hint: string; fixed?: boolean }) {
  const [cue, setCue] = useState<number | null>(null);
  const [score, setScore] = useState(0);
  const [i, setI] = useState(0);
  const [opts, setOpts] = useState(options);
  const { ask, answer } = useAnswer();
  const alive = useAlive();
  const ms = p.window_ms ?? p.warn_ms;
  useEffect(() => {
    (async () => {
      let s = 0;
      for (let k = 0; k < total; k++) {
        if (!alive.current) return;
        const shuffled = fixed ? options : [...options].sort(() => Math.random() - 0.5);
        const target = Math.floor(Math.random() * options.length);
        setOpts(shuffled);
        setCue(target);
        setI(k + 1);
        const a = await ask(ms);
        if (a !== null && shuffled[a] === options[target]) setScore(++s);
        setCue(null);
        await sleep(200);
      }
      if (alive.current) onDone(s);
    })();
  }, []);
  return (
    <>
      <Hud left={`Верно ${score}/${p.need}`} right={`${i}/${total}`} />
      <div className="mg-area mg-choice">
        <div className="mg-cue">{cue === null ? "…" : show(cue)}</div>
        <small className="muted">{hint}</small>
        <div className="mg-opts">
          {opts.map((o, k) => <button key={k} type="button" className="btn" disabled={cue === null} onPointerDown={() => answer(k)}>{o}</button>)}
        </div>
      </div>
    </>
  );
}

export const Arrows = (g: GameProps) => <Choice {...g} total={g.p.rounds} options={ARROWS} show={(i) => ARROWS[i]} hint="Жми такую же стрелку" />;
export const Stance = (g: GameProps) => <Choice {...g} total={g.p.rounds} options={STANCES.slice(0, 3)} show={(i) => STANCES[i]} hint="Повтори стойку" />;
export const Parry = (g: GameProps) => <Choice {...g} total={g.p.strikes} options={ARROWS} show={(i) => `💥${ARROWS[i]}`} hint="Удар оттуда — парируй туда же" fixed />; // кнопки на месте — 550 мс на поиск стрелки не хватало

/** Кроты: красных бить, синих не трогать. */
export function Whack({ p, onDone }: GameProps) {
  const [cell, setCell] = useState<{ i: number; bad: boolean; id: number } | null>(null);
  const [score, setScore] = useState(0);
  const [n, setN] = useState(0);
  const ref = useRef(0);
  const alive = useAlive();
  useEffect(() => {
    (async () => {
      // ровно p.decoys синих (сервер считает цели от этого числа; раньше синие выпадали случайно)
      const plan = Array.from({ length: p.count }, (_, k) => k < (p.decoys ?? 0)).sort(() => Math.random() - 0.5);
      for (let k = 0; k < p.count; k++) {
        if (!alive.current) return;
        setCell({ i: Math.floor(Math.random() * 9), bad: plan[k], id: k });
        setN(k + 1);
        await sleep(p.life_ms);
        setCell(null);
        await sleep(150);
      }
      if (alive.current) onDone(Math.max(0, ref.current));
    })();
  }, []);
  return (
    <>
      <Hud left={`Очков ${Math.max(0, score)}/${p.need}`} right={`${n}/${p.count}`} />
      <div className="mg-area mg-grid">
        {Array.from({ length: 9 }, (_, i) => (
          <button key={i} type="button" className={`mg-cell ${cell?.i === i ? (cell.bad ? "bad" : "hot") : ""}`} onPointerDown={() => {
            if (cell?.i !== i) return;
            ref.current += cell.bad ? -1 : 1;
            setScore(ref.current);
            setCell(null);
          }} />
        ))}
      </div>
    </>
  );
}

/** Счёт: сосчитай вспышки. */
export function Count({ p, onDone }: GameProps) {
  const [flash, setFlash] = useState(false);
  const [opts, setOpts] = useState<number[]>([]);
  const [score, setScore] = useState(0);
  const [r, setR] = useState(0);
  const { ask, answer } = useAnswer();
  const alive = useAlive();
  useEffect(() => {
    (async () => {
      let s = 0;
      for (let k = 0; k < p.rounds; k++) {
        if (!alive.current) return;
        setR(k + 1);
        const total = 2 + Math.floor(Math.random() * (p.flashes - 1));
        for (let f = 0; f < total; f++) {
          setFlash(true); await sleep(p.flash_ms * 0.5); setFlash(false); await sleep(p.flash_ms * rnd(0.6, 1.2));
        }
        const o = [total, total + 1, total - 1, total + 2].sort(() => Math.random() - 0.5);
        setOpts(o);
        const a = await ask(4000);
        if (a !== null && o[a] === total) setScore(++s);
        setOpts([]);
        await sleep(300);
      }
      if (alive.current) onDone(s);
    })();
  }, []);
  return (
    <>
      <Hud left={`Верно ${score}/${p.need}`} right={`${r}/${p.rounds}`} />
      <div className="mg-area mg-choice">
        <div className={`mg-flash ${flash ? "on" : ""}`}>⚡</div>
        <div className="mg-opts">{opts.map((o, k) => <button key={k} type="button" className="btn" onPointerDown={() => answer(k)}>{o}</button>)}</div>
      </div>
    </>
  );
}

/** Пары: найди одинаковые карточки. */
export function Pairs({ p, onDone }: GameProps) {
  const [cards] = useState(() => [...STANCES, "🔥", "⚡"].slice(0, p.pairs).flatMap((e) => [e, e]).sort(() => Math.random() - 0.5));
  const [open, setOpen] = useState<number[]>([]);
  const [done, setDone] = useState<number[]>([]);
  const ref = useRef(0);
  const finished = useRef(false);
  const end = () => { if (!finished.current) { finished.current = true; onDone(ref.current); } };
  const left = useTimer(p.seconds, end);
  const tap = (i: number) => {
    if (open.includes(i) || done.includes(i) || open.length === 2) return;
    const o = [...open, i];
    setOpen(o);
    if (o.length === 2) {
      setTimeout(() => {
        if (cards[o[0]] === cards[o[1]]) {
          ref.current += 1;
          setDone((d) => [...d, ...o]);
          if (ref.current >= p.pairs) end();
        }
        setOpen([]);
      }, 450);
    }
  };
  return (
    <>
      <Hud left={`Пар ${ref.current}/${p.need}`} right={`${left.toFixed(1)} с`} />
      <div className="mg-area mg-grid mg-cards">
        {cards.map((c, i) => <button key={i} type="button" className={`mg-cell ${done.includes(i) ? "done" : ""}`} onPointerDown={() => tap(i)}>{open.includes(i) || done.includes(i) ? c : "❔"}</button>)}
      </div>
    </>
  );
}

/** Ход по кругу 0..1 со скоростью `speed` (оборотов в секунду). */
function usePhase(speed: number) {
  const [ph, setPh] = useState(0);
  const ref = useRef(0);
  useEffect(() => {
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => { ref.current = ((t - t0) / 1000) * speed % 1; setPh(ref.current); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  return { ph, ref };
}

function Taps({ p, onDone, hit, render, label }: GameProps & { hit: (ph: number, round: number) => boolean; render: (ph: number, round: number) => ReactElement; label: string }) {
  const { ph, ref } = usePhase(p.speed);
  const [round, setRound] = useState(0);
  const [score, setScore] = useState(0);
  const s = useRef(0);
  const tap = () => {
    if (hit(ref.current, round)) setScore(++s.current);
    if (round + 1 >= p.rounds) onDone(s.current);
    setRound(round + 1);
  };
  return (
    <>
      <Hud left={`${label} ${score}/${p.need}`} right={`${Math.min(round + 1, p.rounds)}/${p.rounds}`} />
      <div className="mg-area mg-tap" onPointerDown={round < p.rounds ? tap : undefined}>{render(ph, round)}</div>
    </>
  );
}

/** Дыхание: нажми, когда круг на самом вдохе. */
export function Breath(g: GameProps) {
  const size = (ph: number) => 0.5 + 0.5 * Math.sin(ph * Math.PI * 2);
  return <Taps {...g} label="Вдохов" hit={(ph) => size(ph) >= 1 - g.p.zone}
    render={(ph) => <div className="mg-breath" style={{ transform: `scale(${0.35 + 0.65 * size(ph)})` }} />} />;
}

/** Прицел: останови перекрестие в мишени (мишень каждый раунд на новом месте). */
export function Aim(g: GameProps) {
  const [spots] = useState(() => Array.from({ length: g.p.rounds + 1 }, () => rnd(0.1, 0.9 - g.p.size)));
  const pos = (ph: number) => (ph < 0.5 ? ph * 2 : 2 - ph * 2);
  return <Taps {...g} label="Попаданий" hit={(ph, r) => pos(ph) >= spots[r] && pos(ph) <= spots[r] + g.p.size}
    render={(ph, r) => (
      <div className="mg-bar">
        <div className="mg-zone" style={{ left: `${spots[r] * 100}%`, width: `${g.p.size * 100}%` }} />
        <div className="mg-cross" style={{ left: `${pos(ph) * 100}%` }}>✛</div>
      </div>
    )} />;
}

/** Цепочка: следующая цель — сразу после попадания. */
export function Chain({ p, onDone }: GameProps) {
  const [t, setT] = useState({ x: 40, y: 40 });
  const ref = useRef(0);
  const [hits, setHits] = useState(0);
  const left = useTimer(p.seconds, () => onDone(ref.current));
  return (
    <>
      <Hud left={`Попаданий ${hits}/${p.need}`} right={`${left.toFixed(1)} с`} />
      <div className="mg-area">
        <button className="mg-target" style={{ left: `${t.x}%`, top: `${t.y}%`, width: `${p.size * 100}%`, height: `${p.size * 100}%` }}
          onPointerDown={() => { setHits((ref.current += 1)); setT({ x: rnd(4, 96 - p.size * 100), y: rnd(4, 96 - p.size * 100) }); }} />
      </div>
    </>
  );
}

/** Удержание: держи — шкала растёт, отпусти — падает; держи её в зоне. */
export function Hold({ p, onDone }: GameProps) {
  const [v, setV] = useState(0);
  const held = useRef(false);
  const val = useRef(0);
  const score = useRef(0);
  const [inZone, setInZone] = useState(0);
  // 2026-11-20 (жалоба «Удержание · точно» не проходится): зона не уже 12%, шаг шкалы не больше трети зоны
  // и чаще (50 мс) — раньше шаг 6–12% перепрыгивал узкую зону «точно».
  const zone = Math.max(p.zone, 0.12);
  const lo = 0.5 - zone / 2;
  const step = Math.min(p.speed * 0.05, zone / 8); // зона проходится ≥0.4 с (zone/3 — за 150 мс, не удержать)
  const ticks = useRef(0);
  const left = useTimer(p.seconds, () => onDone(score.current));
  useEffect(() => {
    const t = setInterval(() => {
      val.current = Math.max(0, Math.min(1, val.current + (held.current ? 1 : -1) * step));
      if (val.current >= lo && val.current <= lo + zone) {
        ticks.current += 1;
        score.current = Math.floor(ticks.current / 2); // счёт — десятые доли секунды
        setInZone(score.current);
      }
      setV(val.current);
    }, 50);
    return () => clearInterval(t);
  }, []);
  const press = (e: React.PointerEvent) => {
    held.current = true;
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId); // палец не «теряется» при сдвиге
  };
  const release = () => (held.current = false);
  return (
    <>
      <Hud left={`В зоне ${(inZone / 10).toFixed(1)}/${(p.need / 10).toFixed(1)} с`} right={`${left.toFixed(1)} с`} />
      <div className="mg-area mg-tap mg-hold" onPointerDown={press} onPointerUp={release} onPointerCancel={release}
        onLostPointerCapture={release} onContextMenu={(e) => e.preventDefault()}>
        <div className="mg-vbar"><div className="mg-zone" style={{ bottom: `${lo * 100}%`, height: `${zone * 100}%` }} /><div className="mg-fill" style={{ height: `${v * 100}%` }} /></div>
        <small className="muted">Держи палец — шкала растёт</small>
      </div>
    </>
  );
}

/** Сигнал: зелёный — бей, красный — не трогай. */
export function GoNoGo({ p, onDone }: GameProps) {
  const [sig, setSig] = useState<"go" | "no" | null>(null);
  const [score, setScore] = useState(0);
  const [r, setR] = useState(0);
  const { ask, answer } = useAnswer();
  const alive = useAlive();
  useEffect(() => {
    (async () => {
      let s = 0;
      for (let k = 0; k < p.rounds; k++) {
        if (!alive.current) return;
        const bad = Math.random() < p.decoy;
        setSig(bad ? "no" : "go");
        setR(k + 1);
        const a = await ask(p.window_ms);
        if ((a !== null) !== bad) setScore(++s);
        setSig(null);
        await sleep(rnd(250, 500));
      }
      if (alive.current) onDone(s);
    })();
  }, []);
  return (
    <>
      <Hud left={`Верно ${score}/${p.need}`} right={`${r}/${p.rounds}`} />
      <div className={`mg-area mg-tap mg-signal ${sig ?? ""}`} onPointerDown={() => sig && answer(1)}>
        <b>{sig === "go" ? "🟢 БЕЙ" : sig === "no" ? "🔴 СТОЙ" : "…"}</b>
      </div>
    </>
  );
}

/** Двойная: две точки разом — успей обе. */
export function Split({ p, onDone }: GameProps) {
  type Pair = { id: number; a: [number, number]; b: [number, number]; hit: number[] };
  const [pair, setPair] = useState<Pair | null>(null);
  const pairRef = useRef<Pair | null>(null); // два пальца разом: состояние в ref, не в updater (тот может вызваться дважды)
  const [score, setScore] = useState(0);
  const [n, setN] = useState(0);
  const ref = useRef(0);
  const alive = useAlive();
  useEffect(() => {
    (async () => {
      for (let k = 0; k < p.count; k++) {
        if (!alive.current) return;
        pairRef.current = { id: k, a: [rnd(6, 40), rnd(8, 84)], b: [rnd(54, 88), rnd(8, 84)], hit: [] };
        setPair(pairRef.current);
        setN(k + 1);
        await sleep(p.life_ms);
        pairRef.current = null;
        setPair(null);
        await sleep(200);
      }
      if (alive.current) onDone(ref.current);
    })();
  }, []);
  const tap = (w: number) => {
    const cur = pairRef.current;
    if (!cur || cur.hit.includes(w)) return;
    const hit = [...cur.hit, w];
    if (hit.length === 2) {
      setScore((ref.current += 1));
      pairRef.current = null;
    } else pairRef.current = { ...cur, hit };
    setPair(pairRef.current);
  };
  return (
    <>
      <Hud left={`Пар ${score}/${p.need}`} right={`${n}/${p.count}`} />
      <div className="mg-area">
        {pair && [pair.a, pair.b].map((xy, w) => !pair.hit.includes(w) && (
          <button key={`${pair.id}-${w}`} className="mg-dot" style={{ left: `${xy[0]}%`, top: `${xy[1]}%` }} onPointerDown={() => tap(w)} />
        ))}
      </div>
    </>
  );
}

export const NEW_GAMES = {
  order: { name: "Порядок", hint: "Жми кружки по порядку 1, 2, 3…", C: Order },
  arrows: { name: "Стрелки", hint: "Жми такую же стрелку", C: Arrows },
  whack: { name: "Удары по целям", hint: "Красных бей, синих не трогай", C: Whack },
  count: { name: "Счёт", hint: "Сосчитай вспышки", C: Count },
  pairs: { name: "Пары", hint: "Найди одинаковые карточки", C: Pairs },
  stance: { name: "Стойка", hint: "Повтори показанную стойку", C: Stance },
  breath: { name: "Дыхание", hint: "Жми на самом вдохе", C: Breath },
  aim: { name: "Прицел", hint: "Останови прицел в мишени", C: Aim },
  parry: { name: "Парирование", hint: "Удар оттуда — парируй туда же", C: Parry },
  chain: { name: "Цепочка", hint: "Бей цели одну за другой", C: Chain },
  hold: { name: "Удержание", hint: "Держи шкалу в зелёной зоне", C: Hold },
  gonogo: { name: "Сигнал", hint: "Зелёный — бей, красный — стой", C: GoNoGo },
  split: { name: "Двойной удар", hint: "Две цели разом — успей обе", C: Split },
};
