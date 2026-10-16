import { useState } from "react";
import type { ExtrasResult, TrainingResponse } from "../../types";
import { BackHeader, Bar, Panel, Screen, countdown, fmt } from "../../components/ui";
import { ROUTE_DEVELOPMENT } from "../../constants/constants";
import { useAction, useApi } from "../../hooks/useApi";
import "../../styles/development.css";

export function TrainingPage() {
  const { data, status, error, reload } = useApi<TrainingResponse>("/training");
  const { run, busy } = useAction(reload);
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

          {data.schools.length > 0 && (
            <Panel title="ШКОЛЫ СТАТИСТОВ" tone="gold">
              <div className="muted" style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.45, marginBottom: 8 }}>
                Занятие — {fmt(data.school_lesson_price)} NHCoin, раз в час на школу. Учителя покупаются в магазине после их задания.
              </div>
              {data.schools.map((s) => (
                <div key={s.code} className="tr-tech">
                  <div>
                    <b>{s.teacher}</b> <span className="muted" style={{ fontSize: 12 }}>· школа «{s.school}»</span>
                    <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>
                      {s.state === "owned" ? s.effect : s.state === "unlocked" ? "Учитель ждёт в магазине → Обучение" : "Встреть учителя на карте и выполни задание"}
                    </div>
                  </div>
                  {s.state === "owned" && (
                    <button className={`btn gold block ${s.cooldown ? "off" : ""}`} disabled={busy || s.cooldown > 0} onClick={() => run("/training/school/lesson", { school: s.code })}>
                      {s.cooldown ? `Через ${countdown(s.cooldown)}` : `Занятие · ${fmt(data.school_lesson_price)} NHCoin`}
                    </button>
                  )}
                </div>
              ))}
            </Panel>
          )}

          {data.techniques && (
            <Panel title="ТЕХНИКИ" tone="violet">
              <div className="muted" style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.45, marginBottom: 8 }}>
                Уровень техники: оплати тренировку у её учителя → выполни его квест → подними уровень за фрагменты.
                Фрагментов: <b>{fmt(data.techniques.fragments)}</b> · NHCoin: <b>{fmt(data.techniques.coins)}</b>
              </div>
              {data.techniques.items.length === 0 && (
                <div className="muted" style={{ fontSize: 12, fontWeight: 600 }}>Техник пока нет — их дают учителя на карте.</div>
              )}
              {data.techniques.items.map((t) => (
                <div key={t.code} className="tr-tech">
                  <div className="row">
                    <div>
                      <b>{t.name}</b>
                      <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>учитель {t.teacher} · ур. {t.level}{t.next_level ? ` → ${t.next_level}` : ""}</div>
                    </div>
                    {t.stage === "max" && <span className="chip">макс</span>}
                  </div>
                  {(t.stage === "pay" || t.stage === "quest") && (
                    <div className="tr-tasks">
                      {t.tasks.map((k) => (
                        <div key={k.label} className="stat">
                          <span>{k.label}</span>
                          <b>{t.stage === "quest" ? `${fmt(k.done)}/${fmt(k.need)}` : fmt(k.need)}</b>
                        </div>
                      ))}
                    </div>
                  )}
                  {t.stage === "pay" && (
                    <button className={`btn violet block ${data.techniques!.coins >= t.price ? "" : "off"}`} disabled={busy || data.techniques!.coins < t.price} onClick={() => run("/training/technique/pay", { code: t.code })}>
                      Оплатить тренировку · {fmt(t.price)} NHCoin
                    </button>
                  )}
                  {t.stage === "quest" && <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>Квест учителя идёт — он не сгорает.</div>}
                  {t.stage === "level" && (
                    <button className={`btn gold block ${data.techniques!.fragments >= t.fragments_cost ? "" : "off"}`} disabled={busy || data.techniques!.fragments < t.fragments_cost} onClick={() => run("/training/technique/level", { code: t.code })}>
                      Уровень {t.next_level} · {fmt(t.fragments_cost)} фрагментов
                    </button>
                  )}
                </div>
              ))}
            </Panel>
          )}

          {last && (
            <div>
              <div className="section-title" style={{ margin: "0 2px 8px" }}>Прошлая тренировка</div>
              <div className="tr-res">
                <div><b>{fmt(last.stage1)}</b>мощь ×1,2</div>
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
