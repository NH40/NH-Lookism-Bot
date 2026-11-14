import { useState } from "react";
import { imgUrl } from "../../api/api";
import { Panel, countdown, fmt, useCountdown } from "../../components/ui";
import type { TrainingResponse } from "../../types";
import "./Techniques.css";

type School = TrainingResponse["schools"][number];

const CHIP: Record<School["state"], string> = { owned: "занятие", unlocked: "купить!", locked: "задание" };

/** Учителя статистов в Тренировках — как техники: лента карточек с картинкой учителя и подробности выбранного. */
export function SchoolsPanel({ schools, price, run, busy }: {
  schools: School[];
  price: number;
  run: (path: string, body?: unknown) => unknown;
  busy: boolean;
}) {
  const [code, setCode] = useState<string | null>(null);
  // По умолчанию — учитель, у которого есть что сделать: готовое занятие, покупка, сданное задание.
  const first = schools.find((x) => x.state === "owned" && !x.cooldown) ?? schools.find((x) => x.state === "unlocked")
    ?? schools.find((x) => x.quest?.complete) ?? schools[0];
  const s = schools.find((x) => x.code === code) ?? first;
  const cd = useCountdown(s?.cooldown ?? 0);
  if (!s) return null;
  return (
    <Panel title="ШКОЛЫ СТАТИСТОВ" tone="gold">
      <div className="muted tq-empty" style={{ marginBottom: 10 }}>
        Учитель даёт задание на карте. Выполнил — сдай здесь и купи учителя. Занятие — {fmt(price)} NHCoin, раз в час на школу:
        часть статистов получает уровень школы.
      </div>
      <div className="tq-strip">
        {schools.map((x) => (
          <button key={x.code} type="button" className={`tq-pick sc ${x.code === s.code ? "on" : ""}`} onClick={() => setCode(x.code)}>
            <span className="tq-thumb" style={x.image ? { backgroundImage: `url(${imgUrl(x.image, 160)})` } : undefined} />
            <b>{x.teacher}</b>
            <small>«{x.school}»</small>
            <i className={`tq-chip ${x.state === "owned" ? (x.cooldown ? "" : "max") : x.state === "unlocked" ? "level" : "quest"}`}>
              {x.state === "owned" && x.cooldown ? "ждёт" : CHIP[x.state]}
            </i>
          </button>
        ))}
      </div>

      <div className="tq-card sc">
        <div className="tq-banner" style={s.image ? { backgroundImage: `url(${imgUrl(s.image, 720)})` } : undefined}>
          <div className="tq-banner-text">
            <b>{s.teacher}</b>
            <small>школа «{s.school}»</small>
          </div>
        </div>
        <p className="tq-hint"><b>Что даёт:</b> {s.effect}</p>

        {s.state === "locked" && !s.quest && (
          <p className="tq-hint">Встреть учителя на карте («События») и возьми его задание.</p>
        )}
        {s.state === "locked" && s.quest && (
          <>
            <div className="tq-tasks">
              {s.quest.tasks.map((k) => (
                <div key={k.label} className="stat">
                  <span>{k.label}</span>
                  <b style={{ color: k.done >= k.need ? "var(--green-2)" : undefined }}>{fmt(k.done)}/{fmt(k.need)}</b>
                </div>
              ))}
            </div>
            {s.quest.complete ? (
              <button className="btn green block" disabled={busy} onClick={() => run("/training/school/claim", { school: s.code })}>
                Сдать задание
              </button>
            ) : (
              <p className="tq-hint">Задание выполняется в игре, прогресс сохраняется.</p>
            )}
          </>
        )}
        {s.state === "unlocked" && (
          <>
            <p className="tq-hint">Задание сдано — учитель готов взять тебя в ученики.</p>
            <button className="btn gold block" disabled={busy} onClick={() => run("/training/school/buy", { school: s.code })}>
              Купить учителя · {fmt(s.price)} NHCoin
            </button>
          </>
        )}
        {s.state === "owned" && (
          <button className={`btn gold block ${cd ? "off" : ""}`} disabled={busy || cd > 0} onClick={() => run("/training/school/lesson", { school: s.code })}>
            {cd ? `Следующее занятие через ${countdown(cd)}` : `Занятие · ${fmt(price)} NHCoin`}
          </button>
        )}
      </div>
    </Panel>
  );
}
