import { Check, Lock, Plus, Shield, Swords, Zap, Gauge } from "lucide-react";
import type { ReactNode } from "react";
import type { MasteryData } from "../../types";
import { BackHeader, Bar, Panel, Screen, StatRow, countdown, fmt, useCountdown } from "../../components/ui";
import { ROUTE_DEVELOPMENT } from "../../constants/constants";
import { useAction, useApi } from "../../hooks/useApi";
import "./Mastery.css";

const ICONS: Record<string, ReactNode> = {
  strength: <Swords size={16} color="#ff7a8a" />,
  speed: <Zap size={16} color="#7fd4ff" />,
  endurance: <Shield size={16} color="#3ddc84" />,
  technique: <Gauge size={16} color="#a78bfa" />,
};

/** Мастерство: ступени четырёх мастерств, цепочка «Преодоление стены», бой с Томом Ли, тренер. */
export function MasteryPage() {
  const { data, status, error, reload } = useApi<MasteryData>("/mastery");
  const { run, busy } = useAction(reload);
  const cd = useCountdown(data?.battle_cooldown_seconds ?? 0);
  const wait = useCountdown(data?.available_in_seconds ?? 0);

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Мастерство" backLabel="Развитие" to={ROUTE_DEVELOPMENT} />

          <Panel title="Ступени">
            {data.tiers.map((t) => (
              <div key={t.code} className="ms-tier">
                <div className="ms-ico">{ICONS[t.code]}</div>
                <div className="grow">
                  <b>{t.label}</b> <span className="ms-tier-name">{t.tier_label}</span>
                  <small className="muted">{t.effect}</small>
                </div>
                {data.points_free > 0 && (
                  <button
                    className={`btn small ${t.can_invest ? "" : "off"}`}
                    disabled={busy || !t.can_invest}
                    onClick={() => run("/mastery/invest", { mastery: t.code })}
                  >
                    <Plus size={14} />
                  </button>
                )}
              </div>
            ))}
            {data.points_free > 0 && (
              <div className="muted ms-note">
                Невложенных очков: <b>{data.points_free}</b>. Очко — в любое мастерство, но не выше ступени «{data.stage_name}».
              </div>
            )}
          </Panel>

          {data.status === null && (
            <Panel title="Преодоление стены" tone="violet">
              <div className="ms-locked">
                <Lock size={18} />
                Откроется, когда все четыре характеристики дойдут до EXR. Тогда в случайный момент в течение суток придёт
                первое задание.
              </div>
            </Panel>
          )}

          {data.status === "pending" && (
            <Panel title={`Этап ${data.stage} — ${data.stage_name}`} tone="violet">
              <div className="ms-locked">Задание придёт в случайный момент — примерно через {countdown(wait)}.</div>
            </Panel>
          )}

          {data.status === "active" && (
            <Panel title={`Этап ${data.stage}/${data.stages} — ${data.stage_name}`} tone="violet">
              {data.tasks.map((t) => (
                <div key={t.label} className={`ms-task ${t.done ? "done" : ""} ${t.locked ? "locked" : ""}`}>
                  <div className="ms-check">{t.done ? <Check size={14} /> : t.locked ? <Lock size={13} /> : null}</div>
                  <div className="grow">
                    <div className="ms-task-label">{t.label}</div>
                    {t.target > 1 && <Bar value={t.progress} max={t.target} />}
                  </div>
                  {t.target > 1 && <span className="muted ms-count">{t.progress}/{t.target}</span>}
                </div>
              ))}
              <div className="ms-tom">
                <StatRow icon={<Swords size={16} color="#ff7a8a" />} label="Мощь Тома Ли" value={fmt(data.tom_power)} />
                <div className="muted ms-note">Против Тома не работают блок и побег — бьётся лагерь атаки.</div>
                <button
                  className={`btn red block ${data.tom_unlocked && cd <= 0 ? "" : "off"}`}
                  disabled={busy || !data.tom_unlocked || cd > 0}
                  onClick={() => run("/mastery/tom")}
                >
                  {!data.tom_unlocked ? "Том откроется после остальных заданий" : cd > 0 ? `КД сражения ${countdown(cd)}` : "Сразиться с Томом Ли"}
                </button>
              </div>
            </Panel>
          )}

          {data.status === "trainer" && (
            <Panel title="Тренер Том Ли" tone="gold">
              <StatRow label="Очков куплено" value={`${data.points_bought}/${data.points_per_stage}`} />
              <StatRow label="Цена очка" value={`${fmt(data.price ?? 0)} NHCoin`} />
              <StatRow label="У тебя" value={`${fmt(data.nh_coins)} NHCoin`} />
              {data.points_bought < data.points_per_stage ? (
                <button
                  className={`btn gold block ${data.nh_coins >= (data.price ?? 0) ? "" : "off"}`}
                  style={{ marginTop: 8 }}
                  disabled={busy || data.nh_coins < (data.price ?? 0)}
                  onClick={() => run("/mastery/buy")}
                >
                  Купить очко мастерства
                </button>
              ) : (
                <div className="muted ms-note">Все очки этапа куплены — вложи их в ступени выше.</div>
              )}
            </Panel>
          )}

          {data.status === "complete" && (
            <Panel title="Мастерство постигнуто" tone="gold">
              <div className="ms-locked">Все три этапа пройдены — четыре мастерства на высшей ступени.</div>
            </Panel>
          )}
        </div>
      )}
    </Screen>
  );
}
