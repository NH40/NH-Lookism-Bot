// Графики статистики админки: одна серия на график (заголовок её называет — легенда не нужна),
// тонкие столбики со скруглённым верхом, зазор 2px, по нажатию — значение и дата. Цвет — токен макета.
import { useState } from "react";
import { fmt } from "../../components/ui";

export interface Point {
  day: string; // ISO-дата
  value: number;
}

function dayLabel(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}.${m}`;
}

export function BarChart({ data, color, unit = "" }: { data: Point[]; color: string; unit?: string }) {
  const [picked, setPicked] = useState<number | null>(null);
  const W = 320;
  const H = 120;
  const max = Math.max(1, ...data.map((p) => p.value));
  const gap = 2;
  const bw = Math.max(2, (W - gap * (data.length - 1)) / Math.max(1, data.length));
  const current = picked != null ? data[picked] : data[data.length - 1];
  const total = data.reduce((s, p) => s + p.value, 0);
  return (
    <div>
      <div className="row" style={{ alignItems: "baseline", marginBottom: 6 }}>
        <div className="disp" style={{ fontSize: 20 }}>
          {fmt(current?.value ?? 0)}
          {unit}
          <span className="muted" style={{ fontSize: 11, fontWeight: 700, marginLeft: 6 }}>
            {current ? (picked != null ? dayLabel(current.day) : "сегодня") : ""}
          </span>
        </div>
        <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>
          за период {fmt(total)}
          {unit}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H + 16}`} width="100%" role="img" aria-label="график по дням" style={{ display: "block", overflow: "visible" }}>
        <line x1={0} y1={H} x2={W} y2={H} stroke="var(--line-soft)" strokeWidth={1} />
        {data.map((p, i) => {
          const h = p.value > 0 ? Math.max(2, (p.value / max) * (H - 4)) : 0;
          const x = i * (bw + gap);
          const r = Math.min(4, bw / 2, h);
          const y = H - h;
          const path = h
            ? `M${x},${H} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + bw - r},${y} Q${x + bw},${y} ${x + bw},${y + r} L${x + bw},${H} Z`
            : "";
          return (
            <g key={p.day} onClick={() => setPicked(picked === i ? null : i)} style={{ cursor: "pointer" }}>
              {/* Цель нажатия — вся колонка, а не только столбик */}
              <rect x={x} y={0} width={bw + gap} height={H} fill="transparent" />
              {path && <path d={path} fill={color} opacity={picked == null || picked === i ? 1 : 0.45} />}
            </g>
          );
        })}
        {data.length > 0 && (
          <>
            <text x={0} y={H + 13} fontSize={9} fill="var(--muted)">{dayLabel(data[0].day)}</text>
            <text x={W / 2} y={H + 13} fontSize={9} fill="var(--muted)" textAnchor="middle">{dayLabel(data[Math.floor(data.length / 2)].day)}</text>
            <text x={W} y={H + 13} fontSize={9} fill="var(--muted)" textAnchor="end">{dayLabel(data[data.length - 1].day)}</text>
          </>
        )}
      </svg>
    </div>
  );
}
