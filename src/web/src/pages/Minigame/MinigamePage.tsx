import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiPost } from "../../api/api";
import { BackHeader, Panel, Screen } from "../../components/ui";
import { ROUTE_MASTERY, ROUTE_TRAINING } from "../../constants/constants";
import { useApi } from "../../hooks/useApi";
import { gameOf, type GameDef, type P } from "./games";
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
interface Result {
  ok: boolean;
  score: number;
  message?: string;
}
/** Экран: список этапов → правила → отсчёт → игра → итог (каркас 2026-11-23). */
type Phase = "board" | "intro" | "count" | "play" | "result";

const MASTERY_NAMES = ["Сила", "Скорость", "Выносливость", "Техника"];
const fmtNum = (v: number) => Math.round(v).toLocaleString("ru");
const OPEN_ENDED = new Set(["mash", "track", "chain"]);

/** Что нужно сделать — одной строкой для экрана правил и итога. */
function goal(game: string, p: P): string {
  const base = game.split("~")[0];
  if (p.army_power && base === "mash") return `набить мощь ${fmtNum(p.target_power)}`;
  if (base === "dodge") return `пропустить не больше ${p.max_miss} из ${p.strikes ?? p.max_score}`;
  if (base === "hold") return `${(p.need / 10).toFixed(1)} с в зелёной зоне`;
  if (base === "whack") return `${p.need} красных`;
  if (OPEN_ENDED.has(base)) return `${p.need}`; // счёт по таймеру — потолка нет
  return `${p.need} из ${p.max_score}`;
}

/** Итог провала: сколько не хватило — в единицах игры. */
function shortfall(game: string, p: P, score: number): string {
  const base = game.split("~")[0];
  if (base === "dodge") return `Пропущено: ${(p.strikes ?? p.max_score) - score}, можно было ${p.max_miss}`;
  if (base === "hold") return `В зоне: ${(score / 10).toFixed(1)} с из ${(p.need / 10).toFixed(1)} с`;
  if (p.army_power && base === "mash") return `Мощь: ${fmtNum((score * p.army_power) / 40)} из ${fmtNum(p.target_power)}`;
  return `Набрано: ${Math.max(0, score)} из ${p.need} · не хватило ${Math.max(0, p.need - score)}`;
}

/** Мини-игры: этапы занятия техники (`t:<код>`) или 4 испытания мастерства (`m:all`). */
export function MinigamePage() {
  const [sp] = useSearchParams();
  const ctx = sp.get("ctx") ?? "";
  const mastery = ctx.startsWith("m:");
  const { data, status, error, reload } = useApi<Board>(`/minigame?ctx=${encodeURIComponent(ctx)}`);
  const [phase, setPhase] = useState<Phase>("board");
  const [stage, setStage] = useState(0);
  const [run, setRun] = useState<Run | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [count, setCount] = useState(3);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const open = async (i: number) => {
    setBusy(true);
    setMsg(null);
    try {
      setRun(await apiPost<Run>("/minigame/start", { ctx, stage: i }));
      setStage(i);
      setPhase("intro");
    } catch (e) {
      setMsg((e as Error).message);
      setPhase("board");
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    if (phase !== "count") return;
    if (count <= 0) return setPhase("play");
    const t = setTimeout(() => setCount(count - 1), 650);
    return () => clearTimeout(t);
  }, [phase, count]);
  const finish = async (score: number) => {
    if (!run) return;
    const res = await apiPost<{ ok: boolean; message?: string }>("/minigame/finish", { token: run.token, score }).catch((e: Error) => ({
      ok: false,
      message: e.message,
    }));
    setResult({ ok: res.ok, score, message: res.message });
    setPhase("result");
    await reload();
  };

  const back = mastery ? ROUTE_MASTERY : ROUTE_TRAINING;
  const stageName = (i: number, g?: GameDef) => `${mastery ? MASTERY_NAMES[i] : `${i + 1}. ${g?.name ?? ""}`}`;

  if (run && phase !== "board") {
    const g = gameOf(run.game)!;
    const p = run.params;
    if (phase === "play")
      return (
        <div className="page">
          <BackHeader title={g.name} backLabel="Сдаться" to={back} />
          <g.C p={p} onDone={(s) => void finish(s)} />
        </div>
      );
    if (phase === "count")
      return (
        <div className="page">
          <BackHeader title={g.name} backLabel="Сдаться" to={back} />
          <div className="mg-area mg-countdown">
            <b key={count}>{count || "▶"}</b>
          </div>
        </div>
      );
    if (phase === "intro")
      return (
        <div className="page">
          <BackHeader title={stageName(stage, g)} backLabel="Назад" to={back} />
          <Panel title={g.name}>
            <div className="mg-intro">
              <div className="mg-icon">{g.icon}</div>
              <p className="mg-rule">{g.hint}</p>
              {p.army_power ? (
                <p className="muted">
                  {run.game.startsWith("mash")
                    ? "Каждое нажатие — 1/40 мощи твоей армии."
                    : "Пропущенный удар снимает 12% мощи Тома с твоей армии."}
                </p>
              ) : null}
              <div className="mg-goal">
                <span>🎯 Цель: <b>{goal(run.game, p)}</b></span>
                {p.seconds ? <span>⏱ ~{Math.round(p.seconds)} с</span> : null}
              </div>
              <button className="btn gold mg-start" onClick={() => { setCount(3); setPhase("count"); }}>
                ▶ Начать
              </button>
            </div>
          </Panel>
        </div>
      );
    // итог
    const r = result!;
    const next = data?.stages.findIndex((s) => s.playable && !s.done) ?? -1;
    const failedByScore = !r.ok && r.score < p.need; // иначе отказ сервера (истёк токен и т.п.) — показать его текст
    return (
      <div className="page">
        <BackHeader title={stageName(stage, g)} backLabel="К этапам" to={back} />
        <Panel title={r.ok ? "Этап пройден" : "Не вышло"}>
          <div className={`mg-result ${r.ok ? "ok" : "fail"}`}>
            <div className="mg-icon">{r.ok ? "✅" : "❌"}</div>
            <p>{r.ok ? "Отлично — этап засчитан." : failedByScore ? shortfall(run.game, p, r.score) : r.message ?? "Не получилось"}</p>
            {!r.ok && failedByScore && <p className="mg-tip">💡 {g.tip}</p>}
            {r.ok ? (
              next >= 0 ? (
                <button className="btn gold mg-start" disabled={busy} onClick={() => void open(next)}>
                  ▶ Следующий этап
                </button>
              ) : (
                <button className="btn gold mg-start" onClick={() => setPhase("board")}>Готово</button>
              )
            ) : (
              <button className="btn gold mg-start" disabled={busy} onClick={() => void open(stage)}>
                🔁 Ещё раз
              </button>
            )}
            <button className="btn ghost" onClick={() => { setRun(null); setPhase("board"); }}>
              К этапам
            </button>
          </div>
        </Panel>
      </div>
    );
  }

  const total = data?.stages.length ?? 0;
  const doneN = data?.stages.filter((s) => s.done).length ?? 0;
  return (
    <Screen status={status} error={error}>
      <div className="page">
        <BackHeader title={mastery ? "Испытания мастерства" : "Занятие у учителя"} backLabel="Назад" to={back} />
        {msg && <div className="mg-msg">{msg}</div>}
        {data && total === 0 && <Panel title="Готово">Все испытания пройдены — вкладывай очки мастерства.</Panel>}
        {data && total > 0 && (
          <Panel title={mastery ? `Этап ${data.level}` : `Уровень ${data.level}`}>
            <div className="mg-steps">
              <span className="muted">Пройдено {doneN} из {total}</span>
              <div className="mg-dots">
                {data.stages.map((s, i) => (
                  <i key={i} className={s.done ? "done" : s.playable ? "cur" : ""} />
                ))}
              </div>
            </div>
            {data.stages.map((s, i) => {
              const g = gameOf(s.game);
              return (
                <div key={i} className={`mg-stage ${s.done ? "done" : s.playable ? "cur" : "locked"}`}>
                  <span className="mg-stage-ic">{s.done ? "✅" : s.playable ? g?.icon ?? "▶" : "🔒"}</span>
                  <div className="grow">
                    <b>{stageName(i, g)}</b>
                    {mastery && <span className="muted"> · {g?.name}</span>}
                    <small className="muted">{g?.hint}</small>
                  </div>
                  {!s.done && (
                    <button className={`btn small ${s.playable ? "gold" : "off"}`} disabled={busy || !s.playable} onClick={() => void open(i)}>
                      Играть
                    </button>
                  )}
                </div>
              );
            })}
            <small className="muted">Прогресс сохраняется. Провал — переиграй бесплатно.</small>
          </Panel>
        )}
      </div>
    </Screen>
  );
}
