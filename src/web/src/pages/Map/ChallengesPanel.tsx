import { Swords } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet } from "../../api";
import { Panel, countdown } from "../../components/ui";
import { battlePath } from "../../constants/constants";
import { useAction } from "../../hooks/useApi";

// Вызовы (2026-11-20): игроки не понимали, принял ли соперник вызов — теперь статус виден на карте.
interface Item {
  id: number; out: boolean; other: string; target: string; pending: boolean;
  resolution: string | null; won: boolean | null; expires_in: number; ago: number | null;
}

function resultText(it: Item): string {
  const res = it.won === null ? "" : it.won ? " — 🏆 победа" : " — 💀 поражение";
  if (it.resolution === "accepted") return it.out ? `${it.other} принял вызов${res}` : `Ты принял вызов ${it.other}${res}`;
  if (it.resolution === "timeout") return it.out ? `${it.other} не ответил — бился его лагерь защиты${res}` : `Ты не ответил ${it.other} — бился лагерь защиты${res}`;
  return `Вызов с ${it.other} снят (район сменил владельца или кто-то переехал)`;
}

export function ChallengesPanel() {
  const [items, setItems] = useState<Item[]>([]);
  const [tick, setTick] = useState(0);
  const nav = useNavigate();
  const { run, busy } = useAction();
  useEffect(() => {
    let alive = true;
    const load = () => apiGet<{ items: Item[] }>("/arena/challenges").then((d) => alive && (setItems(d.items), setTick(0))).catch(() => undefined);
    load();
    const poll = setInterval(load, 15000);
    const sec = setInterval(() => setTick((t) => t + 1), 1000);
    return () => { alive = false; clearInterval(poll); clearInterval(sec); };
  }, []);
  if (!items.length) return null;
  return (
    <Panel title="ВЫЗОВЫ" tone="red">
      <div className="ef">
        {items.map((it) => (
          <div key={it.id} className={`ef-row ${it.pending ? "live" : ""}`} style={{ cursor: "default" }}>
            <span className="ef-ico"><Swords size={14} /></span>
            <span className="ef-txt">
              {it.pending ? (
                <>
                  <b>{it.out ? `Ты вызвал ${it.other}` : `${it.other} вызвал тебя`} · {it.target}</b>
                  <small>
                    ⏳ {countdown(Math.max(0, it.expires_in - tick))} ·{" "}
                    {it.out ? "ждём ответа; не примет — бой с его лагерем защиты" : "не примешь — район защитит лагерь защиты"}
                  </small>
                </>
              ) : (
                <>
                  <b>{resultText(it)}</b>
                  <small>{it.target}{it.ago !== null ? ` · ${Math.max(1, Math.round(it.ago / 60))} мин назад` : ""}</small>
                </>
              )}
            </span>
            {it.pending && !it.out && (
              <button type="button" className="btn red small" disabled={busy} onClick={async () => {
                const r = (await run("/arena/start/challenge", { challenge_id: it.id })) as { id?: string } | null;
                if (r?.id) nav(battlePath(r.id));
              }}>Принять</button>
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
}
