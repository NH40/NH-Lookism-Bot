import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiPost } from "../../api/api";
import { BackHeader, Panel, Screen } from "../../components/ui";
import { ROUTE_MASTERY, ROUTE_TRAINING } from "../../constants/constants";
import { useApi } from "../../hooks/useApi";
import { GAMES, type P } from "./games";
import "./Minigame.css";

interface Stage {
  game: string;
  done: boolean;
  playable: boolean;
}
interface Board {
  ctx: string;
  code: string;
  level: number;
  stages: Stage[];
}
interface Run {
  token: string;
  game: string;
  params: P;
}

const MASTERY_NAMES = ["Сила", "Скорость", "Выносливость", "Техника"];

/** Мини-игры: этапы занятия техники (`t:<код>`) или 4 испытания мастерства (`m:all`). */
export function MinigamePage() {
  const [sp] = useSearchParams();
  const ctx = sp.get("ctx") ?? "";
  const mastery = ctx.startsWith("m:");
  const { data, status, error, reload } = useApi<Board>(`/minigame?ctx=${encodeURIComponent(ctx)}`);
  const [run, setRun] = useState<Run | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const start = async (stage: number) => {
    setBusy(true);
    setMsg(null);
    try {
      setRun(await apiPost<Run>("/minigame/start", { ctx, stage }));
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const finish = async (score: number) => {
    if (!run) return;
    const res = await apiPost<{ ok: boolean; message?: string }>("/minigame/finish", { token: run.token, score }).catch((e: Error) => ({
      ok: false,
      message: e.message,
    }));
    setRun(null);
    setMsg(res.ok ? "✅ Этап пройден!" : res.message ?? "Не получилось");
    await reload();
  };

  const back = mastery ? ROUTE_MASTERY : ROUTE_TRAINING;
  if (run) {
    const g = GAMES[run.game];
    return (
      <div className="page">
        <BackHeader title={g.name} backLabel="Сдаться" to={back} />
        <p className="muted mg-hint">{g.hint} · нужно {run.params.need}</p>
        <g.C p={run.params} onDone={(s) => void finish(s)} />
      </div>
    );
  }
  return (
    <Screen status={status} error={error}>
      <div className="page">
        <BackHeader title={mastery ? "Испытания мастерства" : "Занятие у учителя"} backLabel="Назад" to={back} />
        {msg && <div className="mg-msg">{msg}</div>}
        {data && data.stages.length === 0 && <Panel title="Готово">Все испытания пройдены — вкладывай очки мастерства.</Panel>}
        {data && data.stages.length > 0 && (
          <Panel title={mastery ? `Этап ${data.level}` : `Уровень ${data.level}: 3 этапа`}>
            {data.stages.map((s, i) => (
              <div key={i} className="mg-stage">
                <div className="grow">
                  <b>{mastery ? MASTERY_NAMES[i] : `Этап ${i + 1}`}</b> · {GAMES[s.game]?.name}
                  <small className="muted">{GAMES[s.game]?.hint}</small>
                </div>
                {s.done ? (
                  <span className="chip">✅</span>
                ) : (
                  <button className={`btn small ${s.playable ? "" : "off"}`} disabled={busy || !s.playable} onClick={() => void start(i)}>
                    Играть
                  </button>
                )}
              </div>
            ))}
            <small className="muted">Прогресс сохраняется. Провал — переиграй бесплатно.</small>
          </Panel>
        )}
      </div>
    </Screen>
  );
}

