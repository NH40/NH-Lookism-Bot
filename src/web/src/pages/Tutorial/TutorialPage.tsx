import { Check, Coins, Hammer, Lock, Swords } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { BackHeader, Bar, Panel, Screen, fmt, useCountdown } from "../../components/ui";
import { ROUTE_MORE, battlePath } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import "./Tutorial.css";

// Лига-обучение (2026-11-19): личная учебная страна и 12 шагов по механикам. Сервисы — те же, что у бота.
interface TutCity { index: number; name: string; owned: boolean[]; buildings: number[]; bot_rank: string; bots: number; whole: boolean; open: boolean }
interface TutData {
  status: "active" | "legacy" | "done"; voluntary: boolean; step: number; total: number; code: string | null; title: string | null;
  text: string | null; lesson: boolean; goto: string | null; reward: string | null; cooldown: number; pending_income: number;
  capacity: number; cities: TutCity[];
}

export function TutorialPage() {
  const { data, status, error, reload } = useApi<TutData>("/tutorial");
  const { run, busy } = useAction(reload);
  const navigate = useNavigate();
  // 2026-11-23: бой обучения — онлайн; сервер отдаёт id боя
  const fight = async (body: { city: number; district?: number }) => {
    const r = (await run("/tutorial/attack", body)) as { battle_id?: string } | null;
    if (r?.battle_id) navigate(battlePath(r.battle_id));
  };
  const cd = useCountdown(data?.cooldown ?? 0);
  const spot = data?.cities.flatMap((c) => c.owned.map((o, i) => (o && c.buildings[i] < data.capacity ? [c.index, i] : null))).find(Boolean) as number[] | undefined;
  const built = data?.cities.reduce((s, c) => s + c.buildings.reduce((a, b) => a + b, 0), 0) ?? 0;
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Обучение" backLabel="Ещё" to={ROUTE_MORE} subtitle={data.status === "active" ? `шаг ${data.step + 1} из ${data.total}` : undefined} />
          {data.status === "legacy" && (
            <Panel title="Учебная страна" tone="gold">
              <div className="tut-text">Гайд по всем механикам на своей учебной карте. За прохождение — небольшая награда, один раз. Ты остаёшься в своей лиге, твоя территория не затрагивается.</div>
              <button type="button" className="btn gold block" style={{ marginTop: 10 }} disabled={busy} onClick={() => run("/tutorial/start")}>Начать обучение</button>
            </Panel>
          )}
          {data.status === "done" && (
            <Panel title="Обучение пройдено" tone="green"><div className="tut-text">Ты выпустился во 2 поколение. Удачи на настоящей карте!</div></Panel>
          )}
          {data.status === "active" && data.code && (
            <>
              <Bar value={data.step} max={data.total} fill="gold" />
              <Panel title={data.title ?? ""} tone="gold">
                <div className="tut-text">{data.text}</div>
                {data.reward && <div className="tut-reward">🎁 {data.reward}</div>}
                <div className="grid-2" style={{ marginTop: 10 }}>
                  {data.goto ? <Link className="btn ghost" to={data.goto}>Открыть раздел</Link> : <span />}
                  <button type="button" className="btn gold" disabled={busy} onClick={() => run("/tutorial/check")}>
                    <Check size={15} />{data.lesson ? "Понятно" : "Проверить"}
                  </button>
                </div>
              </Panel>
              <Panel title="Учебная страна">
                {data.cities.map((c) => {
                  const own = c.owned.filter(Boolean).length;
                  const all = own === c.owned.length;
                  return (
                    <div key={c.index} className={`tut-city ${c.open ? "" : "off"}`}>
                      <div className="tut-city-head">
                        <b>{all ? "✅" : c.open ? "⚔️" : <Lock size={13} />} {c.name}</b>
                        <small>{own}/{c.owned.length} · боты {c.bot_rank} ×{c.bots}{c.whole ? " на весь город" : " в районе"}</small>
                      </div>
                      <div className="tut-districts">
                        {c.owned.map((o, i) => (
                          <button key={i} type="button" className={`tut-d ${o ? "mine" : "bot"}`}
                            disabled={busy || o || !c.open || cd > 0 || c.whole}
                            onClick={() => void fight({ city: c.index, district: i })}>
                            {o ? "🏠" : "🤖"}{c.buildings[i] ? <em>{c.buildings[i]}</em> : null}
                          </button>
                        ))}
                      </div>
                      {c.whole && c.open && !all && (
                        <button type="button" className="btn red small block" style={{ marginTop: 6 }} disabled={busy || cd > 0}
                          onClick={() => void fight({ city: c.index })}>
                          <Swords size={14} /> Взять город целиком
                        </button>
                      )}
                    </div>
                  );
                })}
                {cd > 0 && <div className="tut-sub">⏳ Следующий бой через {cd} с</div>}
                <div className="grid-2" style={{ marginTop: 10 }}>
                  <button type="button" className="btn ghost small" disabled={busy || !spot} onClick={() => spot && run("/tutorial/build", { city: spot[0], district: spot[1] })}>
                    <Hammer size={14} /> Кафе{spot ? ` · район ${spot[1] + 1}` : ""}
                  </button>
                  <button type="button" className="btn green small" disabled={busy || !built} onClick={() => run("/tutorial/collect")}>
                    <Coins size={14} /> Доход {data.pending_income ? fmt(data.pending_income) : ""}
                  </button>
                </div>
                <div className="tut-sub">Тапни по району с ботом 🤖 — бой. Бьются статисты лагеря атаки, потери настоящие.</div>
              </Panel>
            </>
          )}
        </div>
      )}
    </Screen>
  );
}
