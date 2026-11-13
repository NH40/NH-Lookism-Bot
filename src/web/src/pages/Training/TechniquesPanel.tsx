import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { imgUrl } from "../../api/api";
import { Panel, fmt } from "../../components/ui";
import { ROUTE_PLAY } from "../../constants/constants";
import type { TrainingResponse } from "../../types";
import "./Techniques.css";

type Techs = NonNullable<TrainingResponse["techniques"]>;
type Tech = Techs["items"][number];

const STAGE_CHIP: Record<Tech["stage"], string> = { pay: "занятие", quest: "этапы", level: "уровень!", max: "макс" };

/** Новое занятие — одно задание «этапы мини-игр» (3); старые квесты учителя — список заданий. */
function isMinigame(t: Tech): boolean {
  return t.tasks.length === 1 && t.tasks[0].need <= 3;
}

function stagesDone(t: Tech): [number, number] {
  const k = t.tasks[0];
  return k ? [k.done, k.need] : [0, 3];
}

/** Техники в Тренировках: лента карточек для выбора и подробности выбранной. */
export function TechniquesPanel({ d, run, busy }: { d: Techs; run: (path: string, body?: unknown) => unknown; busy: boolean }) {
  const navigate = useNavigate();
  const [code, setCode] = useState<string | null>(null);
  const t = d.items.find((x) => x.code === code) ?? d.items[0];
  return (
    <Panel title="ТЕХНИКИ" tone="violet">
      <div className="tq-wallet">
        <span>🧩 Фрагменты <b>{fmt(d.fragments)}</b></span>
        <span>🪙 NHCoin <b>{fmt(d.coins)}</b></span>
      </div>
      {!t && <div className="muted tq-empty">Техник пока нет — их дают учителя на карте.</div>}
      {t && (
        <>
          <div className="tq-strip">
            {d.items.map((x) => (
              <button key={x.code} type="button" className={`tq-pick ${x.code === t.code ? "on" : ""}`} onClick={() => setCode(x.code)}>
                <span className="tq-thumb" style={x.image ? { backgroundImage: `url(${imgUrl(x.image, 160)})` } : undefined} />
                <b>{x.name}</b>
                <small>ур. {x.level}</small>
                <i className={`tq-chip ${x.stage}`}>{STAGE_CHIP[x.stage]}</i>
              </button>
            ))}
          </div>

          <div className="tq-card">
            <div className="tq-banner" style={t.image ? { backgroundImage: `url(${imgUrl(t.image, 720)})` } : undefined}>
              <div className="tq-banner-text">
                <b>{t.name}</b>
                <small>учитель {t.teacher}</small>
              </div>
            </div>
            <div className="tq-levels">
              {Array.from({ length: 10 }, (_, i) => (
                <i key={i} className={i < t.level ? "done" : i === t.level && t.next_level ? "next" : ""} />
              ))}
              <span>
                ур. <b>{t.level}</b>/10
              </span>
            </div>

            {t.stage === "pay" && (
              <>
                <p className="tq-hint">Оплати занятие у учителя — потом 3 этапа мини-игр и уровень {t.next_level} за {fmt(t.fragments_cost)} фрагментов.</p>
                <button className={`btn violet block ${d.coins >= t.price ? "" : "off"}`} disabled={busy || d.coins < t.price} onClick={() => run("/training/technique/pay", { code: t.code })}>
                  Купить занятие · {fmt(t.price)} NHCoin
                </button>
              </>
            )}
            {t.stage === "quest" && !isMinigame(t) && (
              <>
                <div className="tq-tasks">
                  {t.tasks.map((k) => (
                    <div key={k.label} className="stat">
                      <span>{k.label}</span>
                      <b>{fmt(k.done)}/{fmt(k.need)}</b>
                    </div>
                  ))}
                </div>
                <p className="tq-hint">Старое задание учителя — выполняется в игре, не сгорает.</p>
              </>
            )}
            {t.stage === "quest" && isMinigame(t) && (() => {
              const [done, need] = stagesDone(t);
              return (
                <>
                  <div className="tq-stages">
                    {Array.from({ length: need }, (_, i) => (
                      <span key={i} className={i < done ? "done" : i === done ? "next" : ""}>
                        {i < done ? "✓" : i + 1}
                      </span>
                    ))}
                  </div>
                  <p className="tq-hint">Пройдено этапов: {done} из {need}. Прогресс сохраняется.</p>
                  <button className="btn violet block" onClick={() => navigate(`${ROUTE_PLAY}?ctx=t:${t.code}`)}>
                    🎮 {done ? "Продолжить занятие" : "Начать занятие"}
                  </button>
                </>
              );
            })()}
            {t.stage === "level" && (
              <>
                <p className="tq-hint">Занятие пройдено — поднимай уровень.</p>
                <button className={`btn gold block ${d.fragments >= t.fragments_cost ? "" : "off"}`} disabled={busy || d.fragments < t.fragments_cost} onClick={() => run("/training/technique/level", { code: t.code })}>
                  Уровень {t.next_level} · {fmt(t.fragments_cost)} фрагментов
                </button>
              </>
            )}
            {t.stage === "max" && <p className="tq-hint">Техника прокачана до максимума.</p>}
          </div>
        </>
      )}
    </Panel>
  );
}
