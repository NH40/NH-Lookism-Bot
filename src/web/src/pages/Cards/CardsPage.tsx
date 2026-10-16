import { UserPlus } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { imgUrl } from "../../api";
import type { CardsData, CollectionCard, LineupSlot, PositionSkill } from "../../types";
import { BackHeader, Panel, Screen, fmt } from "../../components/ui";
import { ROUTE_MAP } from "../../constants/constants";
import { useAction, useApi } from "../../hooks/useApi";
import { getWebApp } from "../../telegram";
import { Sheet } from "../../components/Sheet";
import "../../styles/game-screens.css";
import "./Cards.css";

const LEADER = "leader";
const LONG_PRESS_MS = 220;
const MOVE_CANCEL_PX = 8;

const RARITY_TONE: Record<string, string> = {
  legend: "r-gold", peak: "r-gold", absolute: "r-gold",
  new_legend: "r-violet", gen_zero: "r-violet", strong_king: "r-violet",
  king: "r-green", boss: "r-green",
};

function shortLabel(label: string) {
  return label.length > 8 ? `${label.slice(0, 6)}.` : label;
}

interface Drag { card: CollectionCard; x: number; y: number; hover: string | null; snap?: boolean }

// Абсолют Стилист: выбирает перк другого абсолюта (`constant/absolute.ABS_STYLIST`).
const STYLIST_CODE = "some_thing_stylist";

// Навыки позиции у карты: имя, когда работает, эффект с числами её редкости.
function SkillList({ title, skills }: { title: string; skills: PositionSkill[] }) {
  if (!skills.length) return null;
  return (
    <div className="skill-list">
      <div className="skill-title">{title} · {skills.length}</div>
      {skills.map((s) => (
        <div key={s.code} className="skill-row">
          <div className="skill-head"><b>{s.name}</b><span className={`skill-kind k-${s.kind}`}>{s.kind_label}</span></div>
          <div className="skill-text">{s.text}</div>
        </div>
      ))}
    </div>
  );
}

export function CardsPage() {
  const { data, status, error, reload } = useApi<CardsData>("/cards");
  const { run, busy } = useAction(reload);
  const [slot, setSlot] = useState<LineupSlot | null>(null);
  const [posFilter, setPosFilter] = useState<string>("");
  const [rarFilter, setRarFilter] = useState<string>("");
  const [drag, setDrag] = useState<Drag | null>(null);
  const [opened, setOpened] = useState<string | null>(null);
  const openRef = useRef(setOpened);

  const dragRef = useRef<Drag | null>(null);
  const pending = useRef<{ card: CollectionCard; x: number; y: number; timer: number } | null>(null);
  const runRef = useRef(run);
  runRef.current = run;
  const labels = useMemo(() => Object.fromEntries((data?.slots ?? []).map((s) => [s.position, s.label])), [data]);

  const assign = async (code: string) => {
    if (!slot) return;
    if (await run("/cards/position", { position: slot.position, card_code: code })) setSlot(null);
  };
  const clear = async () => {
    if (!slot) return;
    if (await run("/cards/position/clear", { position: slot.position })) setSlot(null);
  };

  // Глобальные слушатели: ведём ghost-элемент за пальцем, на отпускании — drop.
  useEffect(() => {
    const slotAt = (x: number, y: number): string | null => {
      const el = document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-slot]");
      return el?.dataset.slot ?? null;
    };
    const cancelPending = () => {
      if (pending.current) window.clearTimeout(pending.current.timer);
      pending.current = null;
    };
    const onMove = (e: PointerEvent) => {
      const p = pending.current;
      if (p && !dragRef.current) {
        if (Math.hypot(e.clientX - p.x, e.clientY - p.y) > MOVE_CANCEL_PX) {
          cancelPending();
          if (e.pointerType === "mouse") {
            const d = { card: p.card, x: e.clientX, y: e.clientY, hover: null };
            dragRef.current = d;
            setDrag(d);
          }
        }
        return;
      }
      const d = dragRef.current;
      if (!d) return;
      const next = { ...d, x: e.clientX, y: e.clientY, hover: slotAt(e.clientX, e.clientY) };
      dragRef.current = next;
      setDrag(next);
    };
    const onUp = (e: PointerEvent) => {
      const tapped = pending.current && !dragRef.current ? pending.current.card.code : null;
      cancelPending();
      if (tapped) {
        // Короткий тап без сдвига — карточка уника: лагеря и перенос копий.
        openRef.current(tapped);
        return;
      }
      const d = dragRef.current;
      if (!d) return;
      const target = slotAt(e.clientX, e.clientY);
      dragRef.current = null;
      if (target && d.card.positions.includes(target)) {
        setDrag(null);
        void runRef.current("/cards/position", { position: target, card_code: d.card.code });
      } else {
        // невалидный drop — карта «возвращается» на место
        const origin = document.querySelector<HTMLElement>(`[data-code="${d.card.code}"]`)?.getBoundingClientRect();
        setDrag({
          ...d, snap: true, hover: null,
          x: origin ? origin.left + origin.width / 2 : d.x,
          y: origin ? origin.top + origin.height * 0.6 : d.y,
        });
        window.setTimeout(() => setDrag(null), 220);
      }
    };
    const onCancel = () => {
      cancelPending();
      dragRef.current = null;
      setDrag(null);
    };
    // Во время перетаскивания блокируем скролл страницы (touchmove должен быть non-passive).
    const onTouchMove = (e: TouchEvent) => {
      if (dragRef.current) e.preventDefault();
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onCancel);
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onCancel);
      window.removeEventListener("touchmove", onTouchMove);
    };
  }, []);

  const startPress = (e: React.PointerEvent, card: CollectionCard) => {
    if (busy || e.button > 0) return;
    const x = e.clientX;
    const y = e.clientY;
    const begin = () => {
      pending.current = null;
      if (card.free <= 0 && card.placed.length === 0) return; // нечего ставить: ни свободной копии, ни позиции
      getWebApp()?.HapticFeedback?.impactOccurred?.("light");
      const d: Drag = { card, x, y, hover: null };
      dragRef.current = d;
      setDrag(d);
    };
    // Мышь: drag начинается сразу после сдвига; палец: после долгого нажатия.
    const timer = window.setTimeout(begin, e.pointerType === "mouse" ? 2_000_000 : LONG_PRESS_MS);
    pending.current = { card, x, y, timer };
  };

  const current = slot && data ? data.slots.find((s) => s.position === slot.position) ?? slot : null;
  const openedCard = opened && data ? data.collection.find((c) => c.code === opened) ?? null : null;
  const choices = current && data
    ? data.collection.filter(
        (c) => c.positions.includes(current.position) && c.code !== current.card?.code && (c.free > 0 || c.placed.some((p) => p !== current.position)),
      )
    : [];

  const rarities = useMemo(() => {
    const seen = new Map<string, string>();
    for (const c of data?.collection ?? []) if (!seen.has(c.rarity)) seen.set(c.rarity, c.rarity_label);
    return [...seen.entries()];
  }, [data]);
  const shown = (data?.collection ?? []).filter(
    (c) => (!posFilter || c.positions.includes(posFilter)) && (!rarFilter || c.rarity === rarFilter),
  );

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className={`page ${drag && !drag.snap ? "drag-on" : ""}`}>
          <BackHeader
            title="Уники банды"
            subtitle={`в коллекции ${data.owned_total} · на позициях ${data.placed_total}/${data.slots.length}`}
            backLabel="Карта"
            to={ROUTE_MAP}
          />
          <Panel title="РАССТАНОВКА">
            <div className="grid-3">
              {data.slots.map((s) => {
                const valid = !!drag && !drag.snap && drag.card.positions.includes(s.position);
                const cls = `${s.position === LEADER ? "leader" : ""} ${valid ? "valid" : ""} ${valid && drag?.hover === s.position ? "hover" : ""}`;
                return s.card ? (
                  <button key={s.position} type="button" data-slot={s.position} className={`slot ${cls}`} onClick={() => setSlot(s)}>
                    {s.card.image && <img src={imgUrl(s.card.image, 320)} alt={s.card.name} loading="lazy" />}
                    <div className="cap"><span>{s.label}</span>{s.card.name}</div>
                  </button>
                ) : (
                  <button key={s.position} type="button" data-slot={s.position} className={`slot empty ${cls}`} onClick={() => setSlot(s)}>
                    <UserPlus size={22} />
                    {s.label}<br />свободно
                  </button>
                );
              })}
            </div>
          </Panel>

          <Panel title="ЛАГЕРЯ УНИКОВ">
            <div className="muted" style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>
              В атаке: <b>{fmt(data.attack_total)}</b> · в защите: <b>{fmt(data.defense_total)}</b> — копии вне позиций бьются в армии.
            </div>
            {(["attack", "defense"] as const).map((from) => (
              <div key={from} className="grid-3" style={{ marginBottom: 6 }}>
                {data.move_percents.map((p) => (
                  <button key={p} type="button" className="btn small" disabled={busy} onClick={() => run("/cards/move", { from_camp: from, percent: p })}>
                    {from === "attack" ? "⚔️→🛡" : "🛡→⚔️"} {p === 100 ? "всех" : `${p}%`}
                  </button>
                ))}
              </div>
            ))}
          </Panel>

          <div className="chips-row">
            <button type="button" className={`pill ${posFilter === "" ? "on" : ""}`} onClick={() => setPosFilter("")}>Все</button>
            {data.slots.map((s) => (
              <button key={s.position} type="button" className={`pill ${posFilter === s.position ? "on" : ""}`} onClick={() => setPosFilter(s.position)}>{s.label}</button>
            ))}
          </div>
          <div className="chips-row" style={{ marginTop: -6 }}>
            <button type="button" className={`pill ${rarFilter === "" ? "on" : ""}`} onClick={() => setRarFilter("")}>Все</button>
            {rarities.map(([code, label]) => (
              <button key={code} type="button" className={`pill ${rarFilter === code ? "on" : ""}`} onClick={() => setRarFilter(code)}>{label}</button>
            ))}
          </div>

          <div className="grid-4">
            {shown.map((c) => {
              const pos = c.positions.map((p) => shortLabel(labels[p] ?? p));
              return (
                <div
                  key={c.code}
                  data-code={c.code}
                  className={`ccard ${RARITY_TONE[c.rarity] ?? ""} ${c.free <= 0 ? "off" : ""} ${drag?.card.code === c.code ? "lifted" : ""}`}
                  onPointerDown={(e) => startPress(e, c)}
                  onContextMenu={(e) => e.preventDefault()}
                >
                  {c.image && <img src={imgUrl(c.image, 320)} alt={c.name} loading="lazy" draggable={false} />}
                  <div className="pos">{pos.length > 2 ? `${pos.slice(0, 2).join("/")} +${pos.length - 2}` : pos.join("/")}</div>
                  <div className="free">x{c.free}</div>
                  <div className="cap">{c.name}<div>{fmt(c.power)}</div></div>
                </div>
              );
            })}
          </div>
          {shown.length === 0 && <div className="muted" style={{ textAlign: "center", fontSize: 13, fontWeight: 700 }}>Нет карт по фильтру</div>}
          <div className="muted" style={{ fontSize: 11, fontWeight: 700, textAlign: "center" }}>
            Удерживай карту и перетащи на подсвеченную позицию · или нажми позицию и выбери из списка
          </div>
        </div>
      )}

      {drag && drag.card.image && (
        <div className={`drag-ghost ${drag.snap ? "snap" : ""}`} style={{ left: drag.x, top: drag.y }}>
          <img src={imgUrl(drag.card.image, 160)} alt="" />
        </div>
      )}

      {openedCard && (
        <Sheet title={openedCard.name} onClose={() => setOpened(null)}>
          <div className="pick-row" style={{ cursor: "default" }}>
            <div className="pick-thumb">{openedCard.image && <img src={imgUrl(openedCard.image, 160)} alt="" />}</div>
            <div style={{ flex: 1 }}>
              <div className="pick-name">{openedCard.rarity_label} · мощь {fmt(openedCard.power)}</div>
              <div className="pick-sub">
                ⚔️ в атаке {openedCard.attack} · 🛡 в защите {openedCard.defense}
                {openedCard.placed.length ? ` · на позициях ${openedCard.placed.length}` : ""}
              </div>
            </div>
          </div>
          {openedCard.absolute_perk ? (
            <div className="abs-perk">
              <div className="skill-title">♾ Абсолют — не воюет и не гибнет</div>
              <div className="abs-text">{openedCard.absolute_perk}</div>
              {openedCard.code === STYLIST_CODE && data && (
                <div className="abs-choices">
                  {data.stylist_choices.map(([code, name]) => (
                    <button key={code} type="button" className={`pill ${data.stylist_pick === code ? "on" : ""}`} disabled={busy} onClick={() => run("/cards/stylist", { code })}>
                      {name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
          <div className="grid-2" style={{ marginTop: 10 }}>
            <button className={`btn small ${openedCard.attack ? "" : "off"}`} type="button" disabled={busy || !openedCard.attack} onClick={() => run("/cards/move-card", { code: openedCard.code, from_camp: "attack", amount: 1 })}>⚔️→🛡 1</button>
            <button className={`btn small ${openedCard.attack ? "" : "off"}`} type="button" disabled={busy || !openedCard.attack} onClick={() => run("/cards/move-card", { code: openedCard.code, from_camp: "attack" })}>⚔️→🛡 всех</button>
            <button className={`btn small ${openedCard.defense ? "" : "off"}`} type="button" disabled={busy || !openedCard.defense} onClick={() => run("/cards/move-card", { code: openedCard.code, from_camp: "defense", amount: 1 })}>🛡→⚔️ 1</button>
            <button className={`btn small ${openedCard.defense ? "" : "off"}`} type="button" disabled={busy || !openedCard.defense} onClick={() => run("/cards/move-card", { code: openedCard.code, from_camp: "defense" })}>🛡→⚔️ всех</button>
          </div>
          )}
          {openedCard.positions.map((p) => (
            <SkillList key={p} title={`Навыки на позиции «${labels[p] ?? p}»`} skills={openedCard.skills[p] ?? []} />
          ))}
          <div className="muted" style={{ fontSize: 11, fontWeight: 700, marginTop: 8 }}>
            Копии в атаке бьются, когда нападаешь ты; в защите — когда на тебя нападают, а ты не принял бой. Чтобы поставить на позицию — зажми карточку и перетащи.
          </div>
        </Sheet>
      )}

      {current && (
        <Sheet title={current.label} onClose={() => setSlot(null)}>
          <p className="muted" style={{ margin: "0 0 8px", fontSize: 12, fontWeight: 700 }}>{current.description}</p>
          {current.card && (
            <div className="pick-row" style={{ cursor: "default" }}>
              <div className="pick-thumb">{current.card.image && <img src={imgUrl(current.card.image, 160)} alt="" />}</div>
              <div style={{ flex: 1 }}>
                <div className="pick-name">{current.card.name}</div>
                <div className="pick-sub">стоит сейчас · мощь {fmt(current.card.power)}</div>
              </div>
              <button className="btn red small" type="button" disabled={busy} onClick={clear}>Снять</button>
            </div>
          )}
          {current.card && <SkillList title="Навыки на этой позиции" skills={current.skills ?? []} />}
          {choices.length === 0 ? (
            <div className="muted" style={{ fontSize: 13, fontWeight: 700, padding: "12px 0" }}>
              Нет подходящих карт. Крути уников на экране «Банда».
            </div>
          ) : (
            choices.map((c) => (
              <button key={c.code} className="pick-row" type="button" disabled={busy} onClick={() => assign(c.code)}>
                <div className="pick-thumb">{c.image && <img src={imgUrl(c.image, 160)} alt="" loading="lazy" />}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="pick-name">{c.name}</div>
                  <div className="pick-sub">
                    {c.rarity_label} · мощь {fmt(c.power)} · навыков {(c.skills[current.position] ?? []).length} · {c.free > 0 ? `свободно ${c.free}` : `переедет с «${labels[c.placed[0]] ?? c.placed[0]}»`}
                  </div>
                </div>
              </button>
            ))
          )}
        </Sheet>
      )}
    </Screen>
  );
}
