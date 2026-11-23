import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api";
import { Sheet } from "./Sheet";
import { useToast } from "./ui";

// Набор на бой (2026-11-23): в бою и у автобоя — только способности из набора, не больше `max` (8).
// Без настройки в набор идут самые сильные. Там же — «начинать бой на автобое».
interface PerkRow { code: string; name: string; about: string; cost: number; cooldown: number; minigame: string | null; source: string; off: boolean }
interface Loadout { perks: PerkRow[]; max: number; auto_default: boolean }

export function ArenaPerksSheet({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const [data, setData] = useState<Loadout | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    apiGet<Loadout>("/arena/perks").then(setData).catch(() => setData({ perks: [], max: 8, auto_default: false }));
  }, []);
  const call = async (key: string, path: string, body: object) => {
    setBusy(key);
    try {
      setData(await apiPost<Loadout>(path, body));
    } catch (e) {
      toast(String((e as Error).message || e)); // «в наборе уже 8 — сначала выключи другую»
    } finally {
      setBusy(null);
    }
  };
  const on = data?.perks.filter((p) => !p.off).length ?? 0;
  return (
    <Sheet title="Набор в бой" onClose={onClose}>
      {!data ? <div className="skeleton" style={{ height: 200 }} /> : (
        <>
          <button type="button" className={`ap-row ${data.auto_default ? "" : "off"}`} disabled={busy === "auto"}
            onClick={() => call("auto", "/arena/prefs", { auto_default: !data.auto_default })}>
            <span className="ap-txt">
              <b>🤖 Начинать бой на автобое</b>
              <small className="ap-about">В самом бою автобой можно выключить и ходить самому.</small>
            </span>
            <span className={`ap-switch ${data.auto_default ? "on" : ""}`}><i /></span>
          </button>
          <p className="muted" style={{ margin: "10px 0", fontSize: 12, fontWeight: 700 }}>
            В наборе <b>{on} из {data.max}</b>. В бою на панели и у автобоя — только они. Изменения — со следующего боя.
          </p>
          <div className="ap-list">
            {data.perks.map((p) => (
              <button key={p.code} type="button" className={`ap-row ${p.off ? "off" : ""}`} disabled={busy === p.code}
                onClick={() => call(p.code, "/arena/perks", { code: p.code, off: !p.off })}>
                <span className="ap-txt">
                  <b>{p.minigame === "self" ? "🎮 " : p.minigame === "enemy" ? "🎯 " : ""}{p.name}</b>
                  <small>{p.source} · ⚡{p.cost} · перезарядка {p.cooldown} р.</small>
                  <small className="ap-about">{p.about}</small>
                </span>
                <span className={`ap-switch ${p.off ? "" : "on"}`}><i /></span>
              </button>
            ))}
          </div>
        </>
      )}
    </Sheet>
  );
}
