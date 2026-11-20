import { Check, Gauge, Lock, Shield, Swords, Zap } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Sheet } from "../../components/Sheet";
import { useAction, useApi } from "../../hooks/useApi";

// Техники мастерства (2026-11-20, редизайн): у каждого мастерства своя цветная карточка с деревом 3×3,
// цифры техники в бою — в отдельном окне по тапу.
interface Tech { code: string; name: string; about: string; learned: boolean; effects: string[]; energy: number; cooldown: number }
interface Tree { mastery: string; name: string; unlocked: boolean; next_tier: number | null; cost: number | null; tiers: Tech[][] }

export const MASTERY_COLORS: Record<string, string> = {
  strength: "#ff4d6a", speed: "#3d9bff", endurance: "#2ee88a", technique: "#a77bff",
};
const ICONS: Record<string, (c: string) => ReactNode> = {
  strength: (c) => <Swords size={16} color={c} />,
  speed: (c) => <Zap size={16} color={c} />,
  endurance: (c) => <Shield size={16} color={c} />,
  technique: (c) => <Gauge size={16} color={c} />,
};

export function MasteryTechniques() {
  const { data, reload } = useApi<{ fragments: number; trees: Tree[] }>("/mastery/techniques");
  const { run, busy } = useAction(reload);
  const [pick, setPick] = useState<{ tree: Tree; tech: Tech; tier: number } | null>(null);
  if (!data) return null;
  return (
    <div className="mt-wrap">
      <div className="mt-top">
        <b>Техники мастерства</b>
        <span className="mt-frag">🧩 {data.fragments}</span>
      </div>
      <small className="muted mt-hint">На каждой ступени — одна из трёх. Нажми на технику, чтобы увидеть её цифры в бою.</small>
      {data.trees.map((t) => {
        const c = MASTERY_COLORS[t.mastery] ?? "#4fd8ff";
        const learned = t.tiers.flat().filter((x) => x.learned).length;
        return (
          <div key={t.mastery} className={`mt-card ${t.unlocked ? "" : "locked"}`} style={{ ["--c" as string]: c }}>
            <div className="mt-head">
              <span className="mt-ico">{ICONS[t.mastery]?.(c)}</span>
              <b>{t.name}</b>
              <span className="mt-state">
                {!t.unlocked ? <><Lock size={11} /> после стены</> : t.next_tier ? `${learned}/3 · ступень ${t.next_tier}` : "✦ всё изучено"}
              </span>
            </div>
            {t.tiers.map((tier, i) => {
              const open = t.unlocked && t.next_tier === i + 1;
              return (
                <div key={i} className={`mt-tier ${open ? "open" : ""}`}>
                  <span className="mt-num">{["I", "II", "III"][i]}</span>
                  {tier.map((x) => (
                    <button key={x.code} type="button" className={`mt-node ${x.learned ? "on" : open ? "can" : ""}`}
                      onClick={() => setPick({ tree: t, tech: x, tier: i + 1 })}>
                      {x.learned && <Check size={12} className="mt-check" />}
                      {x.name}
                    </button>
                  ))}
                </div>
              );
            })}
            {t.unlocked && t.next_tier && <small className="mt-cost">Следующая ступень: {t.cost} фрагм.</small>}
          </div>
        );
      })}

      {pick && (() => {
        const c = MASTERY_COLORS[pick.tree.mastery] ?? "#4fd8ff";
        const open = pick.tree.unlocked && pick.tree.next_tier === pick.tier && !pick.tech.learned;
        return (
          <Sheet title={pick.tech.name} onClose={() => setPick(null)}>
            <div className="mt-sheet" style={{ ["--c" as string]: c }}>
              <div className="mt-sheet-tag">{pick.tree.name} · ступень {["I", "II", "III"][pick.tier - 1]}</div>
              <p className="mt-about">{pick.tech.about}</p>
              <div className="mt-sheet-sub">В онлайн-бою</div>
              {pick.tech.effects.length ? pick.tech.effects.map((e) => <div key={e} className="mt-eff">◆ {e}</div>)
                : <div className="mt-eff muted">эффект появится с обновлением боёв</div>}
              <div className="mt-chips">
                <span>⚡ энергия {pick.tech.energy}</span>
                <span>⏳ перезарядка {pick.tech.cooldown} р.</span>
              </div>
              {pick.tech.learned ? (
                <div className="mt-done"><Check size={15} /> Изучена</div>
              ) : open ? (
                <button type="button" className="btn block mt-learn" disabled={busy}
                  onClick={async () => { await run("/mastery/techniques/learn", { mastery: pick.tree.mastery, code: pick.tech.code }); setPick(null); }}>
                  Изучить · {pick.tree.cost} фрагм.
                </button>
              ) : (
                <div className="mt-done muted">
                  {!pick.tree.unlocked ? "Откроется после первого этапа стены" : pick.tree.next_tier && pick.tier > pick.tree.next_tier
                    ? "Сначала изучи предыдущую ступень" : "На этой ступени уже выбрана другая техника"}
                </div>
              )}
            </div>
          </Sheet>
        );
      })()}
    </div>
  );
}
