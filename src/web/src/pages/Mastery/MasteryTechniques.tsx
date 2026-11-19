import { useAction, useApi } from "../../hooks/useApi";
import { Panel } from "../../components/ui";

// Техники мастерства (2026-11-19): дерево 3×3 у каждого мастерства, ступень за ступенью — одна из трёх.
interface Tech { code: string; name: string; about: string; learned: boolean }
interface Tree { mastery: string; name: string; unlocked: boolean; next_tier: number | null; cost: number | null; tiers: Tech[][] }

export function MasteryTechniques() {
  const { data, reload } = useApi<{ fragments: number; trees: Tree[] }>("/mastery/techniques");
  const { run, busy } = useAction(reload);
  if (!data) return null;
  return (
    <Panel title={`Техники мастерства · фрагментов ${data.fragments}`} tone="violet">
      <div className="muted" style={{ fontSize: 11, fontWeight: 600 }}>На каждой ступени — одна из трёх. Эффекты в бою — с обновлением битвы.</div>
      {data.trees.map((t) => (
        <div key={t.mastery} style={{ marginTop: 12 }}>
          <b style={{ fontSize: 13 }}>{t.name}</b>
          <span className="muted" style={{ fontSize: 11, fontWeight: 700, marginLeft: 6 }}>
            {!t.unlocked ? "🔒 после первого этапа стены" : t.next_tier ? `ступень ${t.next_tier} · ${t.cost} фрагм.` : "всё изучено"}
          </span>
          {t.tiers.map((tier, i) => (
            <div key={i} className="grid-3" style={{ gap: 6, marginTop: 6 }}>
              {tier.map((x) => {
                const open = t.unlocked && t.next_tier === i + 1;
                return (
                  <button key={x.code} type="button" title={x.about} className={`btn small ${x.learned ? "gold" : open ? "violet" : "ghost off"}`}
                    disabled={busy || !open} onClick={() => run("/mastery/techniques/learn", { mastery: t.mastery, code: x.code })}
                    style={{ minHeight: 44, fontSize: 10.5, lineHeight: 1.2, whiteSpace: "normal" }}>
                    {x.name}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      ))}
    </Panel>
  );
}
