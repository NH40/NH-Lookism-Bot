import { Crown, Maximize2, Minimize2, Minus, Plus, Swords, Users, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { fmt } from "../../components/ui";
import type { Geo, WorldCity, WorldData } from "./worldTypes";
import { clanColor } from "./worldTypes";

// Силуэт страны (2026-11-20): города по реальным координатам, жесты как у карт — палец двигает, щипок/колесо
// приближает, тап по городу — карточка. Размер маркеров постоянный в пикселях при любом зуме.
interface View { x: number; y: number; w: number }

const RADIUS: Record<number, number> = { 4: 6, 8: 7.5, 16: 9.5, 32: 12 };
const RECENT_SECONDS = 600;

function fitView(geo: Geo, pts: [number, number][], aspect: number, focus?: [number, number]): View {
  // Ядро страны: 10–90 перцентиль городов — чтобы далёкие одиночки (Владивосток, Канары) не сжимали карту.
  const q = (arr: number[], t: number) => { const a = [...arr].sort((m, n) => m - n); return a[Math.min(a.length - 1, Math.floor(t * (a.length - 1)))]; };
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  let x0 = q(xs, 0.1), x1 = q(xs, 0.9), y0 = q(ys, 0.1), y1 = q(ys, 0.9);
  const fx0 = Math.min(...xs), fx1 = Math.max(...xs), fy0 = Math.min(...ys), fy1 = Math.max(...ys);
  if ((fx1 - fx0) < (x1 - x0) * 1.8 && (fy1 - fy0) < (y1 - y0) * 1.8) { x0 = fx0; x1 = fx1; y0 = fy0; y1 = fy1; }
  const padX = Math.max(60, (x1 - x0) * 0.2), padY = Math.max(60, (y1 - y0) * 0.2);
  x0 -= padX; x1 += padX; y0 -= padY; y1 += padY;
  let w = x1 - x0;
  if ((y1 - y0) > w * aspect) w = (y1 - y0) / aspect;
  w = Math.min(w, Math.max(geo.w, geo.h / aspect) * 1.05);
  const cx = focus ? Math.min(Math.max(focus[0], x0 + w / 2), x1 - w / 2) : (x0 + x1) / 2;
  const cy = focus ? Math.min(Math.max(focus[1], y0 + (w * aspect) / 2), y1 - (w * aspect) / 2) : (y0 + y1) / 2;
  return { x: (focus && x1 - x0 > w ? cx : (x0 + x1) / 2) - w / 2, y: (focus && y1 - y0 > w * aspect ? cy : (y0 + y1) / 2) - (w * aspect) / 2, w };
}

export function WorldMap({ data, geo, onOpenCity, extra }: {
  data: WorldData; geo: Geo; onOpenCity: (c: WorldCity) => void; extra?: (c: WorldCity) => React.ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 360, h: 420 });
  const [view, setView] = useState<View | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const [full, setFull] = useState(false);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef({ moved: 0, dist: 0 });
  const touched = useRef(false); // пока игрок не трогал карту — подгоняем вид под реальный размер окна
  const pending = useRef<{ dx: number; dy: number; f: number; px: number; py: number } | null>(null);
  const frame = useRef(0);
  // Жесты копятся и применяются раз в кадр — иначе на телефоне каждое движение пальца перерисовывает всю карту.
  const flush = () => {
    frame.current = 0;
    const p = pending.current;
    pending.current = null;
    if (!p) return;
    setView((cur) => {
      const c = cur ?? v;
      const u0 = c.w / size.w;
      let next = { ...c, x: c.x - p.dx * u0, y: c.y - p.dy * u0 };
      if (p.f !== 1) {
        const w = Math.min(maxW, Math.max(minW, next.w / p.f));
        const u1 = w / size.w;
        next = { x: next.x + p.px * (u0 - u1), y: next.y + p.py * (u0 - u1), w };
      }
      return next;
    });
  };
  const queue = (dx: number, dy: number, f = 1, px = 0, py = 0) => {
    const p = pending.current ?? { dx: 0, dy: 0, f: 1, px, py };
    p.dx += dx; p.dy += dy; p.f *= f; p.px = px; p.py = py;
    pending.current = p;
    if (!frame.current) frame.current = requestAnimationFrame(flush);
  };

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const aspect = size.h / size.w;
  const placed = useMemo(() => data.cities.filter((c) => geo.cities[c.name]), [data.cities, geo]);
  const at = (c: WorldCity) => geo.cities[c.name];

  useEffect(() => {
    if ((view && touched.current) || !placed.length) return;
    const home = placed.find((c) => c.id === data.my_city);
    setView(fitView(geo, placed.map(at), aspect, home ? at(home) : undefined));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placed.length, aspect]);

  const v = view ?? { x: 0, y: 0, w: geo.w };
  const minW = 60, maxW = Math.max(geo.w, geo.h / aspect) * 1.3;
  const unit = v.w / size.w; // единиц карты на пиксель

  const zoomAt = (factor: number, px: number, py: number) => setView((cur) => {
    touched.current = true;
    const c = cur ?? v;
    const w = Math.min(maxW, Math.max(minW, c.w / factor));
    const u0 = c.w / size.w, u1 = w / size.w;
    return { x: c.x + px * (u0 - u1), y: c.y + py * (u0 - u1), w };
  });

  const local = (e: { clientX: number; clientY: number }) => {
    const r = box.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  const onDown = (e: React.PointerEvent) => {
    pointers.current.set(e.pointerId, local(e));
    gesture.current.moved = 0;
    touched.current = true;
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      gesture.current.dist = Math.hypot(a.x - b.x, a.y - b.y);
    }
  };
  const onMove = (e: React.PointerEvent) => {
    const prev = pointers.current.get(e.pointerId);
    if (!prev) return;
    const p = local(e);
    pointers.current.set(e.pointerId, p);
    if (pointers.current.size === 1) {
      const dx = p.x - prev.x, dy = p.y - prev.y;
      gesture.current.moved += Math.abs(dx) + Math.abs(dy);
      queue(dx, dy);
    } else if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (gesture.current.dist > 0) queue(0, 0, d / gesture.current.dist, (a.x + b.x) / 2, (a.y + b.y) / 2);
      gesture.current.dist = d;
      gesture.current.moved += 100;
    }
  };
  const onUp = (e: React.PointerEvent) => {
    const wasTap = pointers.current.size === 1 && gesture.current.moved < 8;
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) gesture.current.dist = 0;
    if (!wasTap) return;
    const hit = (e.target as Element).closest?.("[data-city]");
    setSel(hit ? Number(hit.getAttribute("data-city")) : null);
  };
  const onWheel = (e: React.WheelEvent) => {
    const p = local(e);
    touched.current = true;
    queue(0, 0, e.deltaY < 0 ? 1.18 : 1 / 1.18, p.x, p.y);
  };

  const battles = useMemo(() => {
    const m = new Map<number, number>();
    data.battles.forEach((b) => m.set(b.city_id, (m.get(b.city_id) ?? 0) + 1));
    return m;
  }, [data.battles]);
  const recent = useMemo(() => new Set(data.feed.filter((f) => f.ago < RECENT_SECONDS).map((f) => f.city_id)), [data.feed]);
  const selected = sel !== null ? data.cities.find((c) => c.id === sel) ?? null : null;
  const home = data.cities.find((c) => c.id === data.my_city);
  const tokenAt = selected && at(selected) ? at(selected) : home && at(home) ? at(home) : null;
  // Подписи без наложений: крупные города и свой/выбранный — первыми, остальные только если есть место.
  const labels = useMemo(() => {
    const order = [...placed].sort((a, b) => Number(b.id === sel || b.id === data.my_city) - Number(a.id === sel || a.id === data.my_city) || b.districts - a.districts);
    const boxes: [number, number, number, number][] = [];
    const ok = new Set<number>();
    for (const c of order) {
      const [x, y] = at(c);
      const px = (x - v.x) / unit, py = (y - v.y) / unit + (RADIUS[c.districts] ?? 7) + 12;
      const w = c.name.length * 6.4 + 4, h = 13;
      const b: [number, number, number, number] = [px - w / 2, py - h, px + w / 2, py + 2];
      if (boxes.some((o) => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1])) continue;
      boxes.push(b);
      ok.add(c.id);
    }
    return ok;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placed, v.x, v.y, v.w, sel, size.w]);

  return (
    <div className={`wm ${full ? "full" : ""}`}>
      <div ref={box} className="wm-box" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}
        onPointerLeave={(e) => { pointers.current.delete(e.pointerId); }} onWheel={onWheel}>
        <svg width="100%" height="100%" viewBox={`${v.x} ${v.y} ${v.w} ${v.w * aspect}`} preserveAspectRatio="xMidYMid meet">
          <defs>
            <radialGradient id="wm-glow"><stop offset="0" stopColor="#4fd8ff" stopOpacity=".18" /><stop offset="1" stopColor="#4fd8ff" stopOpacity="0" /></radialGradient>
            <pattern id="wm-grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M40 0H0V40" fill="none" stroke="rgba(79,216,255,.06)" strokeWidth="1" />
            </pattern>
          </defs>
          <rect x={-geo.w} y={-geo.h} width={geo.w * 3} height={geo.h * 3} fill="url(#wm-grid)" />
          <path d={geo.path} className="wm-land-glow" style={{ strokeWidth: 7 * unit }} />
          <path d={geo.path} className="wm-land" style={{ strokeWidth: 1.4 * unit }} />
          {data.cities.filter((c) => at(c) && c.clan).map((c) => (
            <circle key={`g${c.id}`} cx={at(c)[0]} cy={at(c)[1]} r={(RADIUS[c.districts] ?? 7) * unit * 3.2}
              fill={clanColor(c.clan, data.my_clan)} opacity={0.12 + c.top_share * 0.12} />
          ))}
          {placed.map((c) => {
            const [x, y] = at(c);
            const r = (RADIUS[c.districts] ?? 7) * unit;
            const col = c.bots === c.districts ? "#5a6b8c" : clanColor(c.clan, data.my_clan);
            const fight = battles.get(c.id) ?? 0;
            const showLabel = labels.has(c.id);
            return (
              <g key={c.id} data-city={c.id} className="wm-city">
                <circle cx={x} cy={y} r={r * 2.4} fill="transparent" />
                {fight > 0 && <circle cx={x} cy={y} r={r * 1.6} className="wm-pulse red" style={{ strokeWidth: 2 * unit }} />}
                {recent.has(c.id) && <circle cx={x} cy={y} r={r * 1.4} className="wm-pulse gold" style={{ strokeWidth: 2 * unit }} />}
                <circle cx={x} cy={y} r={r} fill={col} className={`wm-dot ${c.id === sel ? "sel" : ""} ${c.mine ? "mine" : ""}`}
                  style={{ strokeWidth: (c.id === sel ? 3 : c.mine ? 2.2 : 1.2) * unit }} />
                {c.bots < c.districts && c.bots > 0 && (
                  <path d={arc(x, y, r * 0.55, 1 - c.bots / c.districts)} fill="rgba(255,255,255,.55)" />
                )}
                {c.emperor && <text x={x} y={y - r - 4 * unit} fontSize={14 * unit} textAnchor="middle">👑</text>}
                {fight > 0 && <text x={x + r + 2 * unit} y={y - r * 0.4} fontSize={12 * unit}>⚔️</text>}
                {showLabel && (
                  <text x={x} y={y + r + 12 * unit} fontSize={10.5 * unit} textAnchor="middle" className="wm-label"
                    style={{ strokeWidth: 3 * unit }}>{c.name}</text>
                )}
              </g>
            );
          })}
          {tokenAt && (
            <g className="wm-token" style={{ transform: `translate(${tokenAt[0]}px, ${tokenAt[1]}px)` }}>
              <g transform={`scale(${unit})`}><text x={0} y={-22} fontSize={20} textAnchor="middle">🥷</text></g>
            </g>
          )}
        </svg>

        <div className="wm-ctrl" onPointerDown={(e) => e.stopPropagation()}>
          <button type="button" onClick={() => zoomAt(1.4, size.w / 2, size.h / 2)}><Plus size={16} /></button>
          <button type="button" onClick={() => zoomAt(1 / 1.4, size.w / 2, size.h / 2)}><Minus size={16} /></button>
          <button type="button" onClick={() => { setFull(!full); touched.current = false; setView(null); }}>{full ? <Minimize2 size={15} /> : <Maximize2 size={15} />}</button>
        </div>
        {home && (
          <button type="button" className="wm-home" onPointerDown={(e) => e.stopPropagation()} onClick={() => onOpenCity(home)}>
            <Swords size={15} />Мой город · бои
          </button>
        )}
        <div className="wm-title">
          <b>{data.country_name}</b>
          <small>{data.cities.length} городов · {data.battles.length > 0 ? `⚔️ боёв сейчас: ${data.battles.length}` : "тихо"}</small>
        </div>
      </div>

      {selected && (
        <div className="wm-card" onPointerDown={(e) => e.stopPropagation()}>
          <div className="wm-card-head">
            <span className="wm-chip" style={{ background: clanColor(selected.clan, data.my_clan) }} />
            <b>{selected.name}</b>
            <button type="button" className="btn ghost small" onClick={() => setSel(null)}><X size={14} /></button>
          </div>
          {selected.emperor && (
            <div className="wm-emp"><Crown size={13} />{selected.emperor}
              {selected.emperor_clan && data.clans[selected.emperor_clan] ? ` · клан «${data.clans[selected.emperor_clan]}»` : ""}</div>
          )}
          <div className="wm-stats">
            <span><b>{selected.districts}</b>районов</span>
            <span><b>{selected.bots}</b>у ботов</span>
            <span><b>{selected.owners}</b>банд</span>
            <span><b><Users size={11} /> {fmt(selected.population)}</b>жителей</span>
          </div>
          {selected.top && (
            <small className="muted">Сильнейший: {selected.top} · {Math.round(selected.top_share * 100)}% районов
              {selected.clan && data.clans[selected.clan] ? ` · «${data.clans[selected.clan]}»` : ""}</small>
          )}
          {(battles.get(selected.id) ?? 0) > 0 && (
            <small className="wm-fight"><Swords size={12} /> Идёт боёв: {battles.get(selected.id)}</small>
          )}
          <div className="grid-2" style={{ gap: 6, marginTop: 8 }}>
            <button type="button" className="btn gold small" onClick={() => onOpenCity(selected)}>
              {selected.id === data.my_city ? <><Swords size={14} />В бой</> : "Посмотреть"}
            </button>
            {extra?.(selected)}
          </div>
        </div>
      )}
    </div>
  );
}

// Сектор «доля игроков в городе» поверх точки: белый пирог = районы у банд.
function arc(cx: number, cy: number, r: number, share: number): string {
  if (share >= 0.999) return `M${cx - r},${cy}a${r},${r} 0 1,0 ${2 * r},0a${r},${r} 0 1,0 ${-2 * r},0`;
  const a = share * Math.PI * 2;
  const x = cx + r * Math.sin(a), y = cy - r * Math.cos(a);
  return `M${cx},${cy}L${cx},${cy - r}A${r},${r} 0 ${a > Math.PI ? 1 : 0},1 ${x},${y}Z`;
}
