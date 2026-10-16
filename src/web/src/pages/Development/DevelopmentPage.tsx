import { ChevronRight, Check, Droplet, Dumbbell, Mountain, Lightbulb, Lock, Plus, Sun, Swords, TrendingUp } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type {
  AwakeningData,
  BloodData,
  DevItem,
  DevLevel,
  DevQuest,
  DevTab,
  DevelopmentResponse,
  GeniusData,
  PathData,
  TechniquesData,
} from "../../types";
import { Bar, Panel, Screen, countdown, fmt } from "../../components/ui";
import { ROUTE_MASTERY, ROUTE_TRAINING } from "../../constants/constants";
import { useAction, useApi } from "../../hooks/useApi";
import "../../styles/development.css";

const TABS: { code: DevTab; label: string; icon: ReactNode }[] = [
  { code: "path", label: "Путь", icon: <TrendingUp size={16} /> },
  { code: "techniques", label: "Техники", icon: <Swords size={16} /> },
  { code: "genius", label: "Гений", icon: <Lightbulb size={16} /> },
  { code: "blood", label: "Кровь", icon: <Droplet size={16} /> },
  { code: "awakening", label: "Пробужд.", icon: <Sun size={16} /> },
];

const API = "/development";

function isTab(v: string | null): v is DevTab {
  return TABS.some((t) => t.code === v);
}

export function DevelopmentPage() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab: DevTab = isTab(raw) ? raw : "path";
  const { data, status, error, reload } = useApi<DevelopmentResponse<unknown>>(`${API}?tab=${tab}`);
  const { run, busy } = useAction(reload);
  const post = (path: string, body: unknown = {}) => run(`${API}${path}`, body);
  const ready = data !== null && data.tab === tab;

  return (
    <Screen status={ready || status !== "ready" ? status : "loading"} error={error}>
      <div className="page">
        <div className="seg" role="tablist" style={{ gridTemplateColumns: "repeat(5, minmax(0, 1fr))" }}>
          {TABS.map((t) => (
            <button
              key={t.code}
              type="button"
              role="tab"
              aria-selected={t.code === tab}
              className={`pill ${t.code === tab ? "on" : ""}`}
              onClick={() => setParams({ tab: t.code })}
            >
              {t.icon}
              <span style={{ fontSize: 10, lineHeight: 1.1 }}>{t.label}</span>
            </button>
          ))}
        </div>

        {data && (
          <Link to={ROUTE_TRAINING} className="dev-train">
            <div className="dev-ico"><Dumbbell size={20} /></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 800 }}>Тренировки</div>
              <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>
                личная — {data.training.personal_left ? `через ${countdown(data.training.personal_left)}` : "готова"} · статисты —{" "}
                {data.training.extras_left ? `через ${countdown(data.training.extras_left)}` : "готовы"}
              </div>
            </div>
            <ChevronRight size={18} color="var(--muted)" />
          </Link>
        )}
        {data && (
          <Link to={ROUTE_MASTERY} className="dev-train">
            <div className="dev-ico"><Mountain size={20} /></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 800 }}>Мастерство</div>
              <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>«Преодоление стены», Том Ли и очки мастерства</div>
            </div>
            <ChevronRight size={18} color="var(--muted)" />
          </Link>
        )}

        {ready && data && (
          <>
            {tab === "path" && <PathTab d={data.data as PathData} max={data.max_level} post={post} busy={busy} />}
            {tab === "techniques" && <TechniquesTab d={data.data as TechniquesData} max={data.max_level} post={post} busy={busy} />}
            {tab === "genius" && <GeniusTab d={data.data as GeniusData} max={data.max_level} post={post} busy={busy} />}
            {tab === "blood" && <BloodTab d={data.data as BloodData} max={data.max_level} post={post} busy={busy} />}
            {tab === "awakening" && <AwakeningTab d={data.data as AwakeningData} post={post} busy={busy} />}
          </>
        )}
      </div>
    </Screen>
  );
}

type Post = (path: string, body?: unknown) => Promise<unknown>;

// --- общие блоки ---

function Segments({ level, floor, max }: { level: number; floor: number; max: number }) {
  return (
    <div className="dev-lvl" aria-label={`Уровень ${level} из ${max}`}>
      {Array.from({ length: max }, (_, i) => (
        <span key={i} className={i < level ? "f" : i < floor ? "p" : ""} />
      ))}
    </div>
  );
}

function Buffs({ levels, all }: { levels: DevLevel[]; all: boolean }) {
  const shown = all ? levels : levels.filter((l) => l.state === "done" || l.state === "next");
  return (
    <div style={{ marginTop: 8 }}>
      {shown.map((l) => (
        <div key={l.n} className={`dev-buff ${l.state === "locked" ? "locked" : ""}`}>
          {l.state === "done" ? (
            <Check size={16} color="var(--green)" />
          ) : l.state === "next" ? (
            <Plus size={16} color="var(--cyan)" />
          ) : (
            <Lock size={16} color="var(--muted)" />
          )}
          <div>
            <b>{l.n}.</b> {l.text}
            {l.state === "bought" && <span style={{ color: "var(--violet-2)" }}> · куплен</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function Tasks({ quest }: { quest: DevQuest }) {
  return (
    <div>
      {quest.tasks.map((t) => (
        <div key={t.label} className="dev-task">
          <span>{t.label}</span>
          <span style={{ color: t.done >= t.need ? "var(--green-2)" : "var(--text)" }}>
            {fmt(t.done)} / {fmt(t.need)}
          </span>
        </div>
      ))}
    </div>
  );
}

function OwnedGrid({
  items, selected, onSelect, active, second, children,
}: {
  items: DevItem[];
  selected: string | null;
  onSelect: (code: string) => void;
  active: string | null;
  second?: string | null;
  children?: ReactNode;
}) {
  return (
    <div>
      <div className="section-title" style={{ margin: "0 2px 8px" }}>Твои</div>
      <div className="grid-2">
        {items.map((it) => (
          <button
            key={it.code}
            type="button"
            className={`dev-own ${selected === it.code ? "sel" : ""} ${second === it.code ? "second" : ""}`}
            onClick={() => onSelect(it.code)}
          >
            {it.code === active ? "★ " : it.code === second ? "☆ " : ""}
            <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{shortName(it.name)}</span>
            <span className="lv">{it.level}</span>
          </button>
        ))}
        {children}
      </div>
    </div>
  );
}

function shortName(name: string): string {
  return name.replace(/^Путь\s+/i, "");
}

/** Панель одного элемента развития: уровень, сегменты, баффы, ресурс и «Повысить». */
function ItemPanel({
  title, item, max, resource, have, tone = "blue", onLevelUp, busy, subtitle, children,
}: {
  title: string;
  item: DevItem;
  max: number;
  resource: string;
  have: number;
  tone?: "blue" | "violet";
  onLevelUp?: () => void;
  busy: boolean;
  subtitle?: string;
  children?: ReactNode;
}) {
  const [all, setAll] = useState(false);
  const cost = item.next_cost;
  const enough = cost !== null && have >= cost;
  return (
    <Panel title={title} tone={tone}>
      <div className="row" style={{ alignItems: "flex-start" }}>
        <div>
          <div className="disp" style={{ fontSize: 18, fontWeight: 800 }}>{item.name}</div>
          {subtitle && <div className="muted" style={{ fontSize: 12, fontWeight: 600, marginTop: 3 }}>{subtitle}</div>}
        </div>
        <div className="disp" style={{ fontSize: 22, fontWeight: 800, color: tone === "violet" ? "var(--violet-2)" : "var(--cyan)" }}>
          {item.level}
          <span className="muted" style={{ fontSize: 13 }}>/{max}</span>
        </div>
      </div>
      <Segments level={item.level} floor={item.floor} max={max} />
      {item.floor > item.level && (
        <div className="muted dev-note">
          <span style={{ color: "#c4a6ff" }}>■</span> уровни {item.level + 1}–{item.floor} куплены навсегда — откроются при следующем пробуждении
        </div>
      )}
      {item.theme && <div className="muted" style={{ fontSize: 12, fontWeight: 600, marginTop: 8, lineHeight: 1.4 }}>{item.theme}</div>}
      <Buffs levels={item.levels} all={all} />
      <button type="button" className="btn ghost small" style={{ marginTop: 8 }} onClick={() => setAll(!all)}>
        {all ? "Скрыть закрытые уровни" : "Все уровни"}
      </button>
      {onLevelUp && (
        <div className="row" style={{ marginTop: 12, gap: 10 }}>
          <div style={{ flex: 1 }}>
            {cost !== null ? (
              <>
                <div className="row" style={{ fontSize: 11, fontWeight: 700, marginBottom: 5 }}>
                  <span className="muted">{resource}</span>
                  <span>{fmt(have)} / {fmt(cost)}</span>
                </div>
                <Bar value={have} max={cost} fill={tone === "violet" ? "violet" : "blue"} />
              </>
            ) : (
              <div className="muted" style={{ fontSize: 12, fontWeight: 700 }}>Максимальный уровень</div>
            )}
          </div>
          {cost !== null && (
            <button type="button" className={`btn ${tone === "violet" ? "violet" : ""} ${enough ? "" : "off"}`} disabled={busy} onClick={onLevelUp}>
              Повысить
            </button>
          )}
        </div>
      )}
      {children}
    </Panel>
  );
}

function pick<T extends DevItem>(items: T[], code: string | null, fallback: string | null): T | undefined {
  return items.find((i) => i.code === code) ?? items.find((i) => i.code === fallback) ?? items[0];
}

function SwapButton({ cooldown, onClick, busy, children }: { cooldown: number; onClick: () => void; busy: boolean; children: ReactNode }) {
  return (
    <button type="button" className={`btn ghost block ${cooldown ? "off" : ""}`} style={{ marginTop: 10 }} disabled={busy || cooldown > 0} onClick={onClick}>
      {cooldown ? `${children} — через ${countdown(cooldown)}` : children}
    </button>
  );
}

// --- Путь ---

function PathTab({ d, max, post, busy }: { d: PathData; max: number; post: Post; busy: boolean }) {
  const [sel, setSel] = useState<string | null>(null);

  if (d.stage < 3) {
    return (
      <Panel title="ПУТЬ">
        {d.stage === 0 && (
          <>
            <div style={{ fontSize: 13, fontWeight: 700, lineHeight: 1.45 }}>
              Путь открывается, когда характеристики достаточно прокачаны. Придёт «подтверждение убеждений» — квест, после которого появится убеждение.
            </div>
            <div className="row" style={{ fontSize: 11, fontWeight: 700, margin: "12px 0 5px" }}>
              <span className="muted">Сумма рангов характеристик</span>
              <span>{d.rank_sum} / {d.rank_needed}</span>
            </div>
            <Bar value={d.rank_sum} max={d.rank_needed} />
          </>
        )}
        {d.stage === 1 && (
          <>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>Подтверждение убеждений</div>
            {d.conviction_quest && <Tasks quest={d.conviction_quest} />}
            <button
              type="button"
              className={`btn green block ${d.conviction_quest?.complete ? "" : "off"}`}
              style={{ marginTop: 12 }}
              disabled={busy || !d.conviction_quest?.complete}
              onClick={() => post("/path/conviction")}
            >
              Забрать убеждение
            </button>
          </>
        )}
        {d.stage === 2 && (
          <>
            <div style={{ fontSize: 13, fontWeight: 700, lineHeight: 1.45 }}>
              Убеждение есть. Собери фрагменты пути (их даёт босс Ким Гапрен) и пробуди путь — он выпадет случайно.
            </div>
            <div className="row" style={{ fontSize: 11, fontWeight: 700, margin: "12px 0 5px" }}>
              <span className="muted">Фрагменты пути</span>
              <span>{fmt(d.fragments)} / {fmt(d.awaken_cost)}</span>
            </div>
            <Bar value={d.fragments} max={d.awaken_cost} fill="violet" />
            <div className="dev-tx" style={{ marginTop: 12 }}>
              <button
                type="button"
                className={`btn block ${d.fragments >= d.awaken_cost ? "" : "off"}`}
                disabled={busy || d.fragments < d.awaken_cost}
                onClick={() => post("/path/awaken", { choice: null })}
              >
                Пробудить путь{d.bought.length ? " (случайный)" : ""}
              </button>
              {d.bought.map((b) => (
                <button
                  key={b.code}
                  type="button"
                  className={`btn violet block ${d.fragments >= d.awaken_cost ? "" : "off"}`}
                  disabled={busy || d.fragments < d.awaken_cost}
                  onClick={() => post("/path/awaken", { choice: b.code })}
                >
                  Пробудить: {shortName(b.name)}
                </button>
              ))}
            </div>
          </>
        )}
      </Panel>
    );
  }

  const first = pick(d.owned, sel, d.active);
  const second = d.second_body ? d.owned.find((i) => i.code === d.active2) : undefined;
  const selected = first;
  const isActive = selected?.code === d.active;
  const isSecond = selected?.code === d.active2;
  return (
    <>
      {selected && (
        <ItemPanel
          title="ПУТЬ"
          item={selected}
          max={max}
          resource="Очки пути"
          have={d.points}
          busy={busy}
          subtitle={isActive ? "Активный путь · первое тело" : isSecond ? "Второе тело" : "Не активен"}
          onLevelUp={isActive || isSecond ? () => post("/path/level-up", { slot: isSecond ? 2 : 1 }) : undefined}
        >
          {selected.code === "training" && (isActive || isSecond) && (
            <div className="muted dev-note">
              🏋️ КПД тренировок: +{Math.round(d.training_kpd * 100)}% (потолок уровня +{Math.round(d.training_kpd_cap * 100)}%)
            </div>
          )}
          {!isActive && !isSecond && (
            <>
              <SwapButton cooldown={d.swap_cooldown} busy={busy} onClick={() => post("/path/activate", { code: selected.code, slot: 1 })}>
                Сделать активным
              </SwapButton>
              {d.second_body && (
                <button type="button" className="btn violet block" style={{ marginTop: 8 }} disabled={busy} onClick={() => post("/path/activate", { code: selected.code, slot: 2 })}>
                  Сделать вторым телом
                </button>
              )}
            </>
          )}
        </ItemPanel>
      )}
      {d.second_body && (
        <Panel title="ВТОРОЕ ТЕЛО" badgeMark="2" tone="violet">
          <div className="row">
            <div style={{ fontSize: 13, fontWeight: 700 }}>
              Второй путь: <span style={{ color: "var(--violet-2)" }}>{second ? `${shortName(second.name)} · ${second.level}` : "не выбран"}</span>
            </div>
            <span className="muted" style={{ fontSize: 11, fontWeight: 700 }}>бафы обоих работают</span>
          </div>
          {second && second.code !== selected?.code && (
            <button type="button" className="btn ghost block" style={{ marginTop: 10 }} onClick={() => setSel(second.code)}>
              Открыть второй путь
            </button>
          )}
        </Panel>
      )}
      <OwnedGrid items={d.owned} selected={selected?.code ?? null} onSelect={setSel} active={d.active} second={d.active2}>
        {d.bought.length > 0 && <div className="dev-own dashed">куплено: {d.bought.length}</div>}
      </OwnedGrid>
    </>
  );
}

// --- Техники ---

function TechniquesTab({ d, max, post, busy }: { d: TechniquesData; max: number; post: Post; busy: boolean }) {
  const [sel, setSel] = useState<string | null>(null);
  const selected = pick(d.owned, sel, d.active);
  return (
    <>
      {selected ? (
        <ItemPanel
          title="ТЕХНИКА"
          item={selected}
          max={max}
          resource="Фрагменты УТ"
          have={d.fragments}
          busy={busy}
          subtitle={selected.code === d.active ? "Активна в бою" : "Не активна"}
        >
          <Link to={ROUTE_TRAINING} className="btn block" style={{ marginTop: 8, textDecoration: "none" }}>
            Тренировка у учителя и уровень
          </Link>
          {selected.code !== d.active && (
            <SwapButton cooldown={d.swap_cooldown} busy={busy} onClick={() => post("/technique/activate", { code: selected.code })}>
              Сделать активной
            </SwapButton>
          )}
        </ItemPanel>
      ) : (
        <Panel title="ТЕХНИКА">
          <div style={{ fontSize: 13, fontWeight: 700, lineHeight: 1.45 }}>
            Техник пока нет. На карте периодически появляются учителя — законнекться и выполни его квест.
          </div>
        </Panel>
      )}
      {d.quests.map((q) => (
        <Panel key={q.code} title="КВЕСТ УЧИТЕЛЯ" tone="gold">
          <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 6 }}>{q.title}</div>
          <Tasks quest={q} />
          <button
            type="button"
            className={`btn gold block ${q.complete ? "" : "off"}`}
            style={{ marginTop: 10 }}
            disabled={busy || !q.complete}
            onClick={() => post("/technique/claim", { code: q.code })}
          >
            Получить технику
          </button>
        </Panel>
      ))}
      {d.owned.length > 0 && <OwnedGrid items={d.owned} selected={selected?.code ?? null} onSelect={setSel} active={d.active} />}
    </>
  );
}

// --- Гений ---

function GeniusTab({ d, max, post, busy }: { d: GeniusData; max: number; post: Post; busy: boolean }) {
  const [sel, setSel] = useState<string | null>(null);
  const selected = pick(d.owned, sel, d.active);
  const canRoll = d.fragments >= d.roll_fragments && d.coins >= d.roll_coins;
  return (
    <>
      {selected && (
        <ItemPanel
          title="ГЕНИЙ"
          item={selected}
          max={max}
          resource="Фрагменты гения"
          have={d.fragments}
          busy={busy}
          subtitle={selected.code === d.active ? "Активная гениальность" : "Не активна"}
          onLevelUp={() => post("/genius/level-up", { code: selected.code })}
        >
          {selected.code !== d.active && (
            <SwapButton cooldown={d.swap_cooldown} busy={busy} onClick={() => post("/genius/activate", { code: selected.code })}>
              Сделать активным
            </SwapButton>
          )}
        </ItemPanel>
      )}
      <Panel title="ПРОКРУТ" tone="gold">
        <div style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.45 }} className="muted">
          Новая гениальность ({d.owned.length} из {d.total}). Выпала уже имеющаяся — крутка потеряна.
        </div>
        <div className="row" style={{ fontSize: 12, fontWeight: 700, margin: "10px 0" }}>
          <span>Фрагменты: {fmt(d.fragments)} / {fmt(d.roll_fragments)}</span>
          <span>NHCoin: {fmt(d.coins)} / {fmt(d.roll_coins)}</span>
        </div>
        <button type="button" className={`btn gold block ${canRoll ? "" : "off"}`} disabled={busy || !canRoll} onClick={() => post("/genius/roll")}>
          Крутить
        </button>
      </Panel>
      <OwnedGrid items={d.owned} selected={selected?.code ?? null} onSelect={setSel} active={d.active} />
    </>
  );
}

// --- Родословная ---

function BloodTab({ d, max, post, busy }: { d: BloodData; max: number; post: Post; busy: boolean }) {
  const [open, setOpen] = useState<string | null>(null);

  if (!d.chosen) {
    return (
      <Panel title="РОДОСЛОВНАЯ">
        <div className="muted" style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.45, marginBottom: 8 }}>
          Выбери родословную. Выбор делается один раз — сменить её нельзя.
        </div>
        {(d.options ?? []).map((o) => (
          <div key={o.code} style={{ borderBottom: "1px dashed var(--line-dash)", padding: "8px 0" }}>
            <button
              type="button"
              className="dev-own"
              style={{ width: "100%" }}
              onClick={() => setOpen(open === o.code ? null : o.code)}
              aria-expanded={open === o.code}
            >
              {o.name}
              <ChevronRight size={16} className="lv" />
            </button>
            {open === o.code && (
              <div style={{ padding: "8px 2px 0" }}>
                <div style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.45 }}>{o.description}</div>
                <div className="muted dev-note">Уровень 1: {o.first || "—"}</div>
                <button type="button" className="btn red block" style={{ marginTop: 10 }} disabled={busy} onClick={() => post("/bloodline/choose", { code: o.code })}>
                  Выбрать {o.name}
                </button>
              </div>
            )}
          </div>
        ))}
      </Panel>
    );
  }

  const drops = d.blood_drops ?? 0;
  return (
    <>
      {d.first && (
        <ItemPanel title="РОДОСЛОВНАЯ" item={d.first} max={max} resource="Капли крови" have={drops} busy={busy} subtitle="Первое тело" onLevelUp={() => post("/bloodline/level-up")} />
      )}
      {d.second_body && (
        d.second ? (
          <ItemPanel title="ВТОРОЕ ТЕЛО" item={d.second} max={max} resource="Капли крови" have={drops} tone="violet" busy={busy} subtitle="Вторая родословная" onLevelUp={() => post("/bloodline/level-up2")} />
        ) : (
          <Panel title="ВТОРОЕ ТЕЛО" badgeMark="2" tone="violet">
            <div className="muted" style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
              Выбери вторую родословную (один раз). Бафы обеих действуют сразу.
            </div>
            <div className="grid-2">
              {(d.options2 ?? []).map((o) => (
                <button key={o.code} type="button" className="dev-own second" disabled={busy} onClick={() => post("/bloodline/choose2", { code: o.code })}>
                  {o.name}
                </button>
              ))}
            </div>
          </Panel>
        )
      )}
    </>
  );
}

// --- Пробуждение ---

function AwakeningTab({ d, post, busy }: { d: AwakeningData; post: Post; busy: boolean }) {
  const [confirmUntil, setConfirmUntil] = useState(0);
  const [now, setNow] = useState(Date.now());
  const confirming = confirmUntil > now;

  const ask = async () => {
    const res = (await post("/awakening/request")) as { seconds?: number } | null;
    if (res?.seconds) {
      const t = Date.now();
      setNow(t);
      setConfirmUntil(t + res.seconds * 1000);
      setTimeout(() => setNow(Date.now()), res.seconds * 1000 + 100);
    }
  };
  const confirm = async () => {
    setConfirmUntil(0);
    await post("/awakening/confirm");
  };

  return (
    <>
      <Panel title="ПРОБУЖДЕНИЕ" tone="gold">
        <div className="row" style={{ alignItems: "flex-start" }}>
          <div>
            <div className="disp" style={{ fontSize: 18, fontWeight: 800 }}>Этап {d.level}</div>
            <div className="muted" style={{ fontSize: 12, fontWeight: 600, marginTop: 3 }}>множитель всех бафов ×{d.multiplier}</div>
          </div>
          <div className="disp" style={{ fontSize: 22, fontWeight: 800, color: "var(--gold-2)" }}>
            {d.level}
            <span className="muted" style={{ fontSize: 13 }}>/{d.max}</span>
          </div>
        </div>
        <Segments level={d.level} floor={0} max={d.max} />
        {d.maxed ? (
          <div style={{ fontSize: 13, fontWeight: 700, marginTop: 8 }}>Пробуждение пройдено до конца.</div>
        ) : !d.is_emperor ? (
          <div className="muted" style={{ fontSize: 12, fontWeight: 600, marginTop: 8, lineHeight: 1.45 }}>
            Пробуждение открывается на этапе кулака — стань императором.
          </div>
        ) : (
          <div style={{ marginTop: 8 }}>
            {d.quest && <Tasks quest={d.quest} />}
            <div className="muted dev-note">
              Следующий этап: ×{d.next_multiplier}, потенциал не ниже «{d.next_floor}», капли крови +{d.next_blood}. Прокачка сбрасывается.
            </div>
            {confirming ? (
              <button type="button" className="btn red block" style={{ marginTop: 10 }} disabled={busy} onClick={confirm}>
                Подтвердить пробуждение (необратимо)
              </button>
            ) : (
              <button type="button" className={`btn gold block ${d.ready ? "" : "off"}`} style={{ marginTop: 10 }} disabled={busy || !d.ready} onClick={ask}>
                Пробудиться
              </button>
            )}
          </div>
        )}
      </Panel>
      <Panel title="ЭТАПЫ">
        {d.levels.map((l) => (
          <div key={l.n} className={`dev-buff ${l.state === "locked" ? "locked" : ""}`}>
            {l.state === "done" ? <Check size={16} color="var(--green)" /> : l.state === "next" ? <Plus size={16} color="var(--cyan)" /> : <Lock size={16} color="var(--muted)" />}
            <div>
              <b>{l.n}.</b> ×{l.mult} · {l.text}
            </div>
          </div>
        ))}
      </Panel>
    </>
  );
}
