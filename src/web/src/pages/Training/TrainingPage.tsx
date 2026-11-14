import { useState } from "react";
import { TechniquesPanel } from "./TechniquesPanel";
import { SchoolsPanel } from "./SchoolsPanel";
import type { ExtrasResult, RanksResponse, TrainingResponse } from "../../types";
import { BackHeader, Bar, Panel, Screen, countdown, fmt } from "../../components/ui";
import { ROUTE_DEVELOPMENT } from "../../constants/constants";
import { useAction, useApi } from "../../hooks/useApi";
import "../../styles/development.css";

export function TrainingPage() {
  const { data, status, error, reload } = useApi<TrainingResponse>("/training");
  const ranks = useApi<RanksResponse>("/training/ranks");
  const { run, busy } = useAction(() => {
    reload();
    ranks.reload();
  });
  const [fresh, setLast] = useState<ExtrasResult | null>(null);
  const last = fresh ?? data?.last_extras ?? null;

  const trainExtras = async () => {
    const res = (await run("/training/extras")) as ExtrasResult | null;
    if (res) setLast(res);
  };

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Тренировки" backLabel="Развитие" to={ROUTE_DEVELOPMENT} />

          {ranks.data?.available && (
            <Panel title="РАНГИ СТАТИСТОВ" tone="violet">
              <div className="muted" style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.45, marginBottom: 8 }}>
                Родословная Самдака: запрети переход на следующий ранг или переведи вручную тех, кто дошёл до обычного капа.
              </div>
              {ranks.data.rows.length === 0 && <div className="muted dev-note">В армии пока нет статистов.</div>}
              {ranks.data.rows.map((r) => (
                <div key={r.rank} className="row" style={{ borderBottom: "1px dashed var(--line-dash)", padding: "6px 0", gap: 6 }}>
                  <div style={{ fontSize: 12, fontWeight: 700 }}>
                    {r.rank} · {fmt(r.quantity)}
                    <div className="muted" style={{ fontSize: 11 }}>кап ур. {r.cap} · готовы {fmt(r.ready)}</div>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button type="button" className={`btn small ${r.locked ? "violet" : "ghost"}`} disabled={busy} onClick={() => run("/training/ranks/lock", { rank: r.rank })}>
                      {r.locked ? "Заперт" : "Запереть"}
                    </button>
                    {r.ready > 0 && r.next_rank && (
                      <button type="button" className="btn small gold" disabled={busy} onClick={() => run("/training/ranks/promote", { rank: r.rank })}>
                        На {r.next_rank}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </Panel>
          )}

          <Panel title="ЛИЧНАЯ" tone="green">
            <div className="row" style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 13, fontWeight: 700 }}>
                Очки развития за тренировку
                <div className="muted" style={{ fontSize: 11 }}>
                  потенциал «{data.personal.potential}» · шанс «ничего» {data.personal.nothing_percent}% · на характеристики
                </div>
              </div>
              <div className="disp" style={{ fontSize: 18, fontWeight: 800, color: "var(--green-2)", whiteSpace: "nowrap" }}>
                +{data.personal.min_points}–{data.personal.max_points}
              </div>
            </div>
            <div className="muted" style={{ fontSize: 11, fontWeight: 700, marginBottom: 10 }}>
              Сейчас очков развития: {fmt(data.personal.dev_points)}
            </div>
            {data.personal.left > 0 && (
              <div style={{ marginBottom: 10 }}>
                <Bar value={data.personal.total - data.personal.left} max={data.personal.total} fill="green" />
              </div>
            )}
            <button
              type="button"
              className={`btn green block ${data.personal.left ? "off" : ""}`}
              disabled={busy || data.personal.left > 0}
              onClick={() => run("/training/personal")}
            >
              {data.personal.left ? `Через ${countdown(data.personal.left)}` : "Тренироваться"}
            </button>
          </Panel>

          <Panel title="СТАТИСТЫ">
            <div className="muted" style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.45, marginBottom: 4 }}>
              Каждые {Math.round(data.extras.total / 60)} мин в тренировку случайно попадают{" "}
              <b style={{ color: "var(--text)" }}>{data.extras.coverage_percent}%</b> статистов. Этапы идут по порядку: следующий доступен тем, кто прошёл предыдущий.
            </div>
            {data.extras.stages.map((s) => (
              <div key={s.n} className="tr-stage" style={s.n === data.extras.stages.length ? { borderBottom: "none" } : undefined}>
                <div className="tr-num">{s.n}</div>
                {s.label}
                <span className="tr-pct">{s.percent}%</span>
              </div>
            ))}
            {data.extras.gym_bonus > 0 && (
              <div className="muted" style={{ fontSize: 11, fontWeight: 700, margin: "6px 0 10px" }}>
                +{data.extras.gym_bonus} п.п. к шансам за тренажёрные залы и бонусы развития
              </div>
            )}
            <div className="row" style={{ fontSize: 11, fontWeight: 700, margin: "8px 0 6px" }}>
              <span className="muted">До следующей тренировки</span>
              <span>{data.extras.left ? countdown(data.extras.left) : "готово"}</span>
            </div>
            <div style={{ marginBottom: 10 }}>
              <Bar value={data.extras.left ? data.extras.total - data.extras.left : data.extras.total} max={data.extras.total} />
            </div>
            <button
              type="button"
              className={`btn green block ${data.extras.left || !data.extras.has_extras ? "off" : ""}`}
              disabled={busy || data.extras.left > 0 || !data.extras.has_extras}
              onClick={trainExtras}
            >
              {!data.extras.has_extras ? "Нет статистов" : data.extras.left ? `Через ${countdown(data.extras.left)}` : "Тренировать статистов"}
            </button>
          </Panel>

          {data.schools.length > 0 && <SchoolsPanel schools={data.schools} price={data.school_lesson_price} run={run} busy={busy} />}

          {data.techniques && <TechniquesPanel d={data.techniques} run={run} busy={busy} />}

          {last && (
            <div>
              <div className="section-title" style={{ margin: "0 2px 8px" }}>Прошлая тренировка</div>
              <div className="tr-res">
                <div><b>{fmt(last.stage1)}</b>подняли уровень</div>
                <div><b style={{ color: "var(--gold-2)" }}>{fmt(last.stage2)}</b>новых звёзд</div>
                <div><b style={{ color: "var(--violet-2)" }}>{fmt(last.stage3)}</b>повысили ранг</div>
              </div>
              <div className="muted" style={{ fontSize: 11, fontWeight: 700, marginTop: 6 }}>Участвовало: {fmt(last.attempted)}</div>
            </div>
          )}
        </div>
      )}
    </Screen>
  );
}
