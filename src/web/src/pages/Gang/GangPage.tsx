import { Dices, Shield, Swords, Ticket, Trash2, UserPlus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { imgUrl } from "../../api";
import type { GangData, RollResult } from "../../types";
import { BackHeader, Panel, Screen, countdown, fmt, useCountdown } from "../../components/ui";
import { ROUTE_MAP } from "../../constants/constants";
import { useAction, useApi } from "../../hooks/useApi";
import { Sheet } from "../../components/Sheet";
import "../../styles/game-screens.css";

function rankClass(rank: string): string {
  if (/^(EX|ZZZ|S|A)/.test(rank)) return "r-high";
  if (rank.startsWith("B")) return "r-mid";
  if (rank.startsWith("C")) return "r-low";
  return "";
}

// Отрядов у сильных игроков — сотни: сначала самые первые, остальные — по кнопке.
const SQUADS_SHOWN = 20;

export function GangPage() {
  const { data, status, error, reload } = useApi<GangData>("/gang");
  const { run, busy } = useAction(reload);
  const [from, setFrom] = useState<"attack" | "defense">("attack");
  const [reveal, setReveal] = useState<RollResult | null>(null);
  const recruitRef = useRef<HTMLDivElement>(null);
  const { hash } = useLocation();
  const cd = useCountdown(data?.recruit_cooldown_seconds ?? 0);
  const [allSquads, setAllSquads] = useState(false);
  // Удаление банды — как в боте: запрос → подтверждение в течение N секунд.
  const [deleteSeconds, setDeleteSeconds] = useState(0);
  const deleteLeft = useCountdown(deleteSeconds);
  const askDelete = async () => {
    const r = await run("/gang/delete/request");
    if (r) setDeleteSeconds(Number(r.seconds) || 0);
  };

  useEffect(() => {
    if (data && hash === "#recruit") recruitRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [data, hash]);

  const roll = async () => {
    const result = await run("/gacha/roll");
    if (result) setReveal(result as never);
  };
  const recruit = () => run("/recruit/extra");

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title={`Банда «${data.name}»`} backLabel="Карта" to={ROUTE_MAP} />

          <Panel title="ЛАГЕРЯ">
            <div style={{ display: "flex", gap: 8 }}>
              <div className="camp">
                <div className="camp-title"><Swords size={14} />Атака</div>
                <div className="disp" style={{ fontSize: 17, fontWeight: 800, marginTop: 6 }}>{fmt(data.attack.quantity)}</div>
                <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>мощь {fmt(data.attack.power)}</div>
              </div>
              <div className="camp def">
                <div className="camp-title"><Shield size={14} />Защита</div>
                <div className="disp" style={{ fontSize: 17, fontWeight: 800, marginTop: 6 }}>{fmt(data.defense.quantity)}</div>
                <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>мощь {fmt(data.defense.power)}</div>
              </div>
            </div>
            <div className="muted" style={{ fontSize: 11, fontWeight: 700, margin: "10px 0 6px" }}>
              Перевести из {from === "attack" ? "атаки в защиту" : "защиты в атаку"}
            </div>
            <div className="grid-4" style={{ gap: 6 }}>
              {data.move_percents.map((p) => (
                <button key={p} className="mv" type="button" disabled={busy} onClick={() => run("/gang/move", { from_camp: from, percent: p })}>
                  {p === 100 ? "Все" : `${p}%`}
                </button>
              ))}
              <button className="mv" type="button" onClick={() => setFrom(from === "attack" ? "defense" : "attack")}>⇄ обратно</button>
            </div>
          </Panel>

          <Panel title="ОТРЯДЫ">
            {data.squads.length === 0 && <div className="muted" style={{ fontSize: 13, fontWeight: 700 }}>Отрядов пока нет — заверби статистов ниже.</div>}
            {(allSquads ? data.squads : data.squads.slice(0, SQUADS_SHOWN)).map((sq) => (
              <div className="sq" key={`${sq.rank}-${sq.stars}-${sq.training_level}-${sq.school}-${sq.school_level}`}>
                <div className={`rk ${rankClass(sq.rank)}`}>{sq.rank}</div>
                <div className="sq-body">
                  {sq.rank}
                  {sq.stars > 0 && <span className="star"> {"★".repeat(Math.min(sq.stars, 5))}</span>}
                  {sq.training_level > 0 && ` · ур. ${sq.training_level}`}
                  {sq.school && ` · школа ${sq.school}${sq.school_level ? ` ${sq.school_level}` : ""}`}
                  <div className="muted" style={{ fontSize: 11 }}>атака {fmt(sq.attack)} · защита {fmt(sq.defense)}</div>
                </div>
                <b>×{fmt(sq.total)}</b>
              </div>
            ))}
            {data.cards_quantity > 0 && (
              <div className="muted" style={{ fontSize: 11, fontWeight: 700, marginTop: 8 }}>+ копий уников в армии: {fmt(data.cards_quantity)}</div>
            )}
            {data.squads.length > SQUADS_SHOWN && (
              <button className="btn ghost small block" type="button" style={{ marginTop: 8 }} onClick={() => setAllSquads(!allSquads)}>
                {allSquads ? "Свернуть" : `Показать все (${data.squads.length})`}
              </button>
            )}
          </Panel>

          <div ref={recruitRef}>
            <Panel title="ВЕРБОВКА" tone="gold">
              <div className="grid-2">
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <button className={`btn block ${cd > 0 ? "off" : ""}`} type="button" disabled={busy || cd > 0} onClick={recruit}>
                    <UserPlus size={16} />Статисты
                  </button>
                  <div className="muted" style={{ fontSize: 11, fontWeight: 700, textAlign: "center" }}>
                    {cd > 0 ? `через ${countdown(cd)}` : `до ранга ${data.recruit_ceiling_rank}`}
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <button className={`btn gold block ${data.tickets.count <= 0 ? "off" : ""}`} type="button" disabled={busy || data.tickets.count <= 0} onClick={roll}>
                    <Dices size={16} />Крутка уника
                  </button>
                  <div className="muted" style={{ fontSize: 11, fontWeight: 700, textAlign: "center", display: "flex", justifyContent: "center", alignItems: "center", gap: 4 }}>
                    <Ticket size={12} />тикетов {data.tickets.count}/{data.tickets.cap}
                    {data.tickets.next_in_seconds ? ` · +1 через ${countdown(data.tickets.next_in_seconds)}` : ""}
                  </div>
                </div>
              </div>
            </Panel>
          </div>
        </div>
      )}

      {data && (
        <div className="page" style={{ paddingTop: 0 }}>
          <Panel title="ОПАСНАЯ ЗОНА" tone="red" badgeMark="!">
            <p className="muted" style={{ margin: "0 0 10px", fontSize: 11, fontWeight: 700, lineHeight: 1.45 }}>
              Сбросится весь прогресс: банда, районы и бизнес на них, статисты, уники, характеристики, мастерство, NHCoin.
              Останутся потенциал, пробуждение, родословная и талант.
            </p>
            <button className="btn red block" type="button" disabled={busy} onClick={askDelete}><Trash2 size={16} />Удалить банду</button>
          </Panel>
        </div>
      )}
      {deleteSeconds > 0 && deleteLeft > 0 && (
        <Sheet title="Удалить банду?" onClose={() => setDeleteSeconds(0)}>
          <p className="muted" style={{ margin: "0 0 12px", fontSize: 13, fontWeight: 700 }}>
            Это необратимо. Подтверждение действует ещё {deleteLeft} с. Потом в чате с ботом заново выберешь страну и город.
          </p>
          <div className="grid-2">
            <button className="btn ghost" type="button" onClick={() => setDeleteSeconds(0)}>Отмена</button>
            <button className="btn red" type="button" disabled={busy} onClick={async () => { if (await run("/gang/delete/confirm")) setDeleteSeconds(0); }}>Да, удалить всё</button>
          </div>
        </Sheet>
      )}
      {reveal && (
        <Sheet title="Новый уник" onClose={() => setReveal(null)}>
          <div className="reveal-art">
            {reveal.card.image && <img src={imgUrl(reveal.card.image, 480)} alt={reveal.card.name} />}
          </div>
          <div style={{ textAlign: "center" }}>
            <div className="disp" style={{ fontSize: 17, fontWeight: 800 }}>{reveal.card.name}</div>
            <div style={{ color: "var(--gold-2)", fontSize: 12, fontWeight: 800, margin: "4px 0" }}>{reveal.card.rarity_label}</div>
            <div className="muted" style={{ fontSize: 12, fontWeight: 700 }}>
              мощь {fmt(reveal.card.power)} · копий у тебя: {reveal.copies}
              {reveal.free ? " · тикет вернулся" : ""}
            </div>
          </div>
          {reveal.absolute_perk && <div className="reveal-perk">♾ {reveal.absolute_perk}</div>}
          {reveal.skills.map((g) => g.skills.length > 0 && (
            <div key={g.position} className="reveal-skills">
              <div className="reveal-skills-title">Навыки · {g.label} · {g.skills.length}</div>
              {g.skills.map((sk) => (
                <div key={sk.name} className="reveal-skill"><b>{sk.name}</b> <span className="muted">· {sk.kind_label}</span><div className="muted">{sk.text}</div></div>
              ))}
            </div>
          ))}
          <div className="grid-2" style={{ marginTop: 14 }}>
            <button className="btn ghost" type="button" onClick={() => setReveal(null)}>Закрыть</button>
            <button className={`btn gold ${reveal.tickets <= 0 ? "off" : ""}`} type="button" disabled={busy || reveal.tickets <= 0} onClick={roll}>
              Ещё ({reveal.tickets})
            </button>
          </div>
        </Sheet>
      )}
    </Screen>
  );
}
