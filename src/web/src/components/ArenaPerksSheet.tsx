import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api";
import { Sheet } from "./Sheet";

// Способности для онлайн-боёв (2026-11-20, просьба игрока): отключённые не попадают в бой и автоатака их не жмёт.
interface PerkRow { code: string; name: string; about: string; cost: number; cooldown: number; minigame: string | null; source: string; off: boolean }

export function ArenaPerksSheet({ onClose }: { onClose: () => void }) {
  const [perks, setPerks] = useState<PerkRow[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => { apiGet<{ perks: PerkRow[] }>("/arena/perks").then((d) => setPerks(d.perks)).catch(() => setPerks([])); }, []);
  const toggle = async (p: PerkRow) => {
    setBusy(p.code);
    try {
      setPerks((await apiPost<{ perks: PerkRow[] }>("/arena/perks", { code: p.code, off: !p.off })).perks);
    } finally {
      setBusy(null);
    }
  };
  const on = perks?.filter((p) => !p.off).length ?? 0;
  return (
    <Sheet title="Способности в бою" onClose={onClose}>
      <p className="muted" style={{ margin: "0 0 10px", fontSize: 12, fontWeight: 700 }}>
        Выключенные не появятся в онлайн-боях, и автоатака не будет их использовать. Изменения — со следующего боя.
        {perks && ` Включено ${on} из ${perks.length}.`}
      </p>
      {!perks ? <div className="skeleton" style={{ height: 200 }} /> : (
        <div className="ap-list">
          {perks.map((p) => (
            <button key={p.code} type="button" className={`ap-row ${p.off ? "off" : ""}`} disabled={busy === p.code} onClick={() => toggle(p)}>
              <span className="ap-txt">
                <b>{p.minigame === "self" ? "🎮 " : p.minigame === "enemy" ? "🎯 " : ""}{p.name}</b>
                <small>{p.source} · ⚡{p.cost} · перезарядка {p.cooldown} р.</small>
                <small className="ap-about">{p.about}</small>
              </span>
              <span className={`ap-switch ${p.off ? "" : "on"}`}><i /></span>
            </button>
          ))}
        </div>
      )}
    </Sheet>
  );
}
