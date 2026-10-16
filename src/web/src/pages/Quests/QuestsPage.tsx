import {
  Check, ChevronLeft, ChevronRight, Coins, Crown, Dices, Dumbbell, FlaskConical, Gem,
  Gift, GraduationCap, Hammer, Handshake, Lock, Package, ScrollText, Shield, Skull,
  Swords, Target, TrendingUp, UserPlus, type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Bar, Panel, Screen, countdown, fmt } from "../../components/ui";
import { useAction, useApi } from "../../hooks/useApi";
import type { PassData, PassTrack, QuestsData, RewardItem } from "../../types";
import "./Quests.css";

const TASK_ICON: Record<string, LucideIcon> = {
  win_pve: Swords, win_pvp: Swords, pvp_call: Swords, war_win: Swords, boss_win: Skull,
  personal_train: Dumbbell, train_extras: Dumbbell, recruit: UserPlus, contract: UserPlus,
  roll: Dices, casino: Dices, poker_hand: Dices, collect: Coins, income: Coins, deposit: Coins,
  clan_donate: Coins, build: Hammer, school_lesson: GraduationCap, potion: FlaskConical,
  ex_deal: Handshake, ex_list: Handshake, storage: Package, garrison: Shield,
  stat_invest: TrendingUp, dev_level: TrendingUp, bp_claim: Gift,
};

const RES_SHORT: Record<string, string> = {
  coins: "NHC", tickets: "тик.", dev_pts: "о.р.", path_pts: "о.п.", path_fr: "фр.",
  tech_fr: "фр.т.", gen_fr: "фр.г.", blood: "кр.", donate: "дон.", scroll: "свиток",
};

function Rewards({ items }: { items: RewardItem[] }) {
  const r = items[0];
  if (!r) return <small>—</small>;
  const label = r.code === "scroll" ? (r.amount > 1 ? `${r.amount} свит.` : "свиток") : `${fmt(r.amount)} ${RES_SHORT[r.code] ?? ""}`;
  return <small>{label.trim()}</small>;
}

function PassPanel({ data, reload, page, setPage }: {
  data: PassData;
  reload: () => void;
  page: number | undefined;
  setPage: (p: number) => void;
}) {
  const { run, busy } = useAction(reload);
  const claim = (track: PassTrack, level: number) => run("/battle-pass/claim", { track, level });
  const claimAll = (track: PassTrack) => run("/battle-pass/claim-all", { track });

  const cell = (track: PassTrack, e: PassData["entries"][number]): ReactNode => {
    const prem = track === "prem";
    const claimed = prem ? e.premium_claimed : e.free_claimed;
    const open = e.level <= data.level && (!prem || data.is_premium);
    const state = claimed ? "claimed" : open ? "ready" : "locked";
    return (
      <button
        key={`${track}${e.level}`}
        className={`bp-cell ${prem ? "prem" : ""} ${state} ${e.level === data.level ? "current" : ""}`}
        disabled={busy || state !== "ready"}
        onClick={() => claim(track, e.level)}
      >
        {e.level}
        <Rewards items={prem ? e.premium : e.free} />
        {claimed && <Check size={13} className="tick" />}
        {state === "locked" && <Lock size={11} className="lock" />}
      </button>
    );
  };

  const claimBtn = (track: PassTrack, claimable: boolean) =>
    claimable && (
      <button className={`btn small ${track === "prem" ? "gold" : "green"}`} disabled={busy} onClick={() => claimAll(track)}>
        Забрать всё · {track === "prem" ? "премиум" : "бесплатно"}
      </button>
    );

  const cur = page ?? data.page;
  return (
    <Panel title={`BATTLE PASS · СЕЗОН ${data.season_number}`} tone="gold">
      <div className="row">
        <div className="disp bp-level">
          {data.level} <span className="muted">уровень{data.loop_position ? ` · цикл ${data.loop_position}/10` : ""}</span>
        </div>
        <div className="bp-meta">
          <span><span className="bp-boost">Буст ×{data.boost.multiplier}</span> · {data.boost.used}/{data.boost.cap} ур. сегодня</span>
          <div className="muted">сезон: ещё {countdown(data.season_left)}</div>
        </div>
      </div>
      <div style={{ margin: "10px 0 12px" }}><Bar value={data.xp_in_level} max={data.level_xp} fill="gold" /></div>
      <div className="bp-row">{data.entries.map((e) => cell("prem", e))}</div>
      <div className="bp-row" style={{ marginTop: 6 }}>{data.entries.map((e) => cell("free", e))}</div>

      {(data.premium_claimable || data.free_claimable) && (
        <div className="bp-claims">{claimBtn("prem", data.premium_claimable)}{claimBtn("free", data.free_claimable)}</div>
      )}

      <div className="bp-pager">
        <button aria-label="Назад" disabled={cur <= 1} onClick={() => setPage(cur - 1)}><ChevronLeft size={18} /></button>
        <span>{cur} / {data.pages_max}</span>
        <button aria-label="Вперёд" disabled={cur >= data.pages_max} onClick={() => setPage(cur + 1)}><ChevronRight size={18} /></button>
      </div>

      {!data.is_premium && (
        <button className="btn gold block" style={{ marginTop: 12 }} disabled={busy} onClick={() => run("/battle-pass/buy-premium")}>
          <Crown size={16} />Открыть премиум — {data.premium_price} <Gem size={14} />
        </button>
      )}
    </Panel>
  );
}

type SheetKind = "reroll" | "scroll" | null;

function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="sheet-back" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <h3 className="disp">{title}</h3>
        {children}
        <button className="btn ghost block" onClick={onClose}>Закрыть</button>
      </div>
    </div>
  );
}

export function QuestsPage() {
  const [page, setPage] = useState<number | undefined>(undefined);
  const [sheet, setSheet] = useState<SheetKind>(null);
  const pass = useApi<PassData>(`/battle-pass${page ? `?page=${page}` : ""}`);
  const quests = useApi<QuestsData>("/quests");
  const reloadAll = () => {
    void pass.reload();
    void quests.reload();
  };
  const { run, busy } = useAction(() => {
    setSheet(null);
    reloadAll();
  });

  const status = pass.status !== "ready" ? pass.status : quests.status;
  const q = quests.data;
  const d = pass.data;
  const canReroll = q && (q.full_reroll_available || q.swaps_left > 0) && q.completed < q.total;

  return (
    <Screen status={status} error={pass.error ?? quests.error}>
      {d && q && (
        <div className="page">
          <PassPanel data={d} reload={reloadAll} page={page} setPage={setPage} />

          <div className="row" style={{ padding: "0 2px" }}>
            <div>
              <div className="disp" style={{ fontSize: 15, fontWeight: 800 }}>Задания дня</div>
              <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>
                {q.completed}/{q.total}
                {q.completed < q.total && q.next_multiplier > 1 ? ` · следующее ×${q.next_multiplier}` : ""} · новые через {countdown(q.resets_in)}
              </div>
            </div>
            {canReroll && <button className="mini" type="button" onClick={() => setSheet("reroll")}>Реролл</button>}
          </div>

          <div className="qlist">
            {q.quests.map((it) => {
              const Icon = TASK_ICON[it.task] ?? Target;
              return (
                <div key={it.slot} className={`quest ${it.done ? "done" : ""}`}>
                  <div className="qi">{it.done ? <Check size={18} /> : <Icon size={18} />}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="row" style={{ fontSize: 13, fontWeight: 800 }}>
                      <span>{it.label}<span className={`tier tier-${it.tier}`} /></span>
                      {!it.done && <span className="muted" style={{ fontSize: 11 }}>+{it.xp}</span>}
                    </div>
                    {it.done ? (
                      <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>
                        {fmt(it.target)}/{fmt(it.target)} · +{it.xp} опыта
                      </div>
                    ) : (
                      <>
                        <div style={{ marginTop: 6 }}><Bar value={it.progress} max={it.target} fill="blue" /></div>
                        <div className="muted" style={{ fontSize: 11, fontWeight: 700, marginTop: 4 }}>
                          {fmt(it.progress)} / {fmt(it.target)}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {q.scrolls > 0 && (
            <div className="scroll-panel">
              <span><ScrollText size={14} style={{ verticalAlign: -2 }} /> Свитков пропуска: {q.scrolls}</span>
              <button className="btn small violet" onClick={() => setSheet("scroll")}>Использовать</button>
            </div>
          )}

          {q.is_admin && (
            <button className="btn ghost block" disabled={busy} onClick={() => run("/quests/admin-complete")}>
              🧪 Выполнить все задания (админ)
            </button>
          )}
        </div>
      )}

      {sheet === "reroll" && q && (
        <Sheet title="Реролл заданий" onClose={() => setSheet(null)}>
          {q.full_reroll_available && (
            <button className="btn green block" disabled={busy} onClick={() => run("/quests/reroll-all")}>
              Заменить все невыполненные
            </button>
          )}
          {q.swaps_left > 0 && (
            <>
              <div className="muted" style={{ fontSize: 12 }}>
                Или заменить по одному (осталось {q.swaps_left} из {q.swaps_per_day}):
              </div>
              {q.quests.filter((x) => !x.done).map((x) => (
                <button key={x.slot} className="sheet-item" disabled={busy} onClick={() => run("/quests/swap", { slot: x.slot })}>
                  <span>{x.label}</span>
                  <span className="muted">{fmt(x.progress)}/{fmt(x.target)}</span>
                </button>
              ))}
            </>
          )}
        </Sheet>
      )}

      {sheet === "scroll" && q && (
        <Sheet title="Свиток пропуска" onClose={() => setSheet(null)}>
          {q.skippable.length === 0 && <div className="muted">Нет заданий развития, которые можно пропустить.</div>}
          {q.skippable.map((x) => (
            <button key={x.id} className="sheet-item" disabled={busy} onClick={() => run("/quests/scroll", { quest_id: x.id })}>
              <span>{x.label}</span>
              <ScrollText size={14} />
            </button>
          ))}
        </Sheet>
      )}
    </Screen>
  );
}
