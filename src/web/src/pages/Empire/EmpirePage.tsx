import { Crown, Eye, Shield, Swords } from "lucide-react";
import { useCallback, useState } from "react";
import { apiGet, ApiError } from "../../api";
import type { EmpireData, EmpireIncomingWar, EmpireRuler, EmpireSubject, EmpireSubjectRate, EmpireWarTarget, EmpireWarTargets, SabotageAction } from "../../types";
import { BackHeader, Panel, Screen, StatRow, countdown, fmt, useCountdown, useToast } from "../../components/ui";
import { ROUTE_MAP } from "../../constants/constants";
import { Sheet } from "../../components/Sheet";
import { useAction, useApi } from "../../hooks/useApi";
import "./Empire.css";

// Империя — отдельный экран за кнопкой на «Карте» (пользователь 2026-10-14): император — налоги, персональные
// ставки, войны императоров; игрок в городе императора — саботаж (свой КД у каждого действия).

function Rates({ min, max, value, onPick, busy }: { min: number; max: number; value: number; onPick: (p: number) => void; busy: boolean }) {
  const steps: number[] = [];
  for (let p = min; p <= max; p += 10) steps.push(p);
  return (
    <div className="emp-rates">
      {steps.map((p) => (
        <button key={p} type="button" className={`pill ${p === value ? "on" : ""}`} style={{ minHeight: 40 }} disabled={busy} onClick={() => p !== value && onPick(p)}>
          {p}%
        </button>
      ))}
    </div>
  );
}

function TaxTab({ ruler, min, max, onChanged }: { ruler: EmpireRuler; min: number; max: number; onChanged: () => void }) {
  const toast = useToast();
  const { run, busy } = useAction(onChanged);
  const [nick, setNick] = useState("");
  const [subject, setSubject] = useState<EmpireSubjectRate | null>(null);

  const find = async (username: string) => {
    if (!username.trim()) return;
    try {
      setSubject(await apiGet<EmpireSubjectRate>(`/empire/subject?username=${encodeURIComponent(username.trim())}`));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : String(err), "err");
    }
  };
  const setPersonal = async (percent: number | null) => {
    if (!subject) return;
    if (await run("/empire/personal", { user_id: subject.user_id, percent })) setSubject(null);
  };

  return (
    <>
      <Panel title="ОБЩИЙ НАЛОГ" tone="gold" badgeMark="%">
        <Rates min={min} max={max} value={ruler.tax_percent} busy={busy} onPick={(p) => run("/empire/tax", { percent: p })} />
        <p className="emp-note">Налог игрок теряет — он уходит тебе. Сверху +10% от дохода каждого (у него не вычитается).</p>
        <StatRow label="Собрано всего" value={<span style={{ color: "var(--gold-2)" }}>{fmt(ruler.collected)}</span>} />
        <StatRow label="Владения" value={`${fmt(ruler.holdings)} зд.`} />
      </Panel>

      <Panel title="ПЕРСОНАЛЬНЫЕ СТАВКИ">
        <div className="row" style={{ gap: 8 }}>
          <input className="emp-input" placeholder="@ник подданного" value={nick} onChange={(e) => setNick(e.currentTarget.value.replace(/\s/g, ""))} />
          <button className="btn small" type="button" onClick={() => find(nick)}>Найти</button>
        </div>
        {ruler.overrides.length === 0 ? (
          <p className="emp-note" style={{ textAlign: "center" }}>Пока все платят общий налог. Найди игрока — и назначь ему свою ставку {min}–{max}%.</p>
        ) : (
          <div style={{ marginTop: 10 }}>
            {ruler.overrides.map((o) => (
              <button key={`${o.username}-${o.name}`} type="button" className="emp-row" style={{ width: "100%", color: "inherit", font: "inherit", textAlign: "left" }} disabled={!o.username} onClick={() => o.username && find(o.username)}>
                <div className="grow"><b>{o.name}</b>{o.username && <small>@{o.username}</small>}</div>
                <span className="disp" style={{ color: "var(--gold-2)" }}>{o.percent}%</span>
              </button>
            ))}
            {ruler.overrides_total > ruler.overrides.length && <p className="emp-note">…и ещё {ruler.overrides_total - ruler.overrides.length}</p>}
          </div>
        )}
      </Panel>

      <Panel title={`ДИВЕРСИИ ЗА ${ruler.sabotage_hours} Ч`} tone="violet">
        <div className="row" style={{ gap: 10, justifyContent: "flex-start" }}>
          <Eye size={22} color="var(--red-2, #ff8aa0)" />
          <div>
            <div style={{ fontSize: 14, fontWeight: 800 }}>Попыток: {ruler.sabotage_total} · удачных: {ruler.sabotage_success}</div>
            <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>кто — неизвестно; шпион на позиции раскрывает</div>
          </div>
        </div>
      </Panel>

      {subject && (
        <Sheet title={`Ставка: ${subject.name}`} onClose={() => setSubject(null)}>
          <p className="muted" style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 700 }}>
            Сейчас — {subject.percent}% {subject.own ? "(персональная)" : "(общая)"}
          </p>
          <Rates min={min} max={max} value={subject.own ? subject.percent : -1} busy={busy} onPick={(p) => setPersonal(p)} />
          {subject.own && (
            <button className="btn ghost block" type="button" style={{ marginTop: 10 }} disabled={busy} onClick={() => setPersonal(null)}>
              Вернуть общий налог
            </button>
          )}
        </Sheet>
      )}
    </>
  );
}

function IncomingWar({ war, onChanged }: { war: EmpireIncomingWar; onChanged: () => void }) {
  const left = useCountdown(war.expires_in_seconds);
  const { run, busy } = useAction(onChanged);
  return (
    <Panel title="ПРОТИВ ТЕБЯ ВОЙНА" tone="red" badgeMark="!">
      <p style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 700 }}>
        Император <b>{war.attacker}</b> бросил вызов. Не примешь за {countdown(left)} — бой пройдёт против твоего лагеря защиты.
      </p>
      <button className="btn red block" type="button" disabled={busy || left <= 0} onClick={() => run("/empire/war/accept", { war_id: war.war_id })}>
        <Swords size={16} />Принять бой
      </button>
    </Panel>
  );
}

function WarTab({ ruler, onChanged }: { ruler: EmpireRuler; onChanged: () => void }) {
  const [page, setPage] = useState(0);
  const { data, reload } = useApi<EmpireWarTargets>(`/empire/war/targets?page=${page}`);
  const done = useCallback(async () => { await reload(); onChanged(); }, [reload, onChanged]);
  const { run, busy } = useAction(done);
  const [target, setTarget] = useState<EmpireWarTarget | null>(null);
  const cd = useCountdown(ruler.war_cooldown_seconds);

  return (
    <>
      {ruler.incoming && <IncomingWar war={ruler.incoming} onChanged={onChanged} />}
      <Panel title="ИМПЕРАТОРЫ" badgeMark="⚔">
        {cd > 0 && <p className="emp-note" style={{ margin: "0 0 10px" }}>Следующий вызов — через {countdown(cd)}.</p>}
        {!data ? (
          <p className="emp-note">Загружаю…</p>
        ) : data.items.length === 0 ? (
          <p className="emp-note" style={{ textAlign: "center" }}>Других императоров пока нет.</p>
        ) : (
          data.items.map((t) => (
            <div key={t.user_id} className="emp-row">
              <Crown size={20} color="var(--gold-2)" />
              <div className="grow">
                <b>{t.name}</b>
                <small>{t.country ?? "—"} · городов {t.cities} · казна {fmt(t.treasury)}</small>
                {t.shield_seconds > 0 && <small><Shield size={10} /> щит ещё {countdown(t.shield_seconds)}</small>}
              </div>
              <button className="btn small" type="button" disabled={busy || cd > 0 || t.shield_seconds > 0} onClick={() => setTarget(t)}>Вызов</button>
            </div>
          ))
        )}
        {data && (data.page > 0 || data.has_more) && (
          <div className="pager">
            <span>Стр. {data.page + 1}</span>
            <span>
              <button type="button" disabled={data.page <= 0} onClick={() => setPage(data.page - 1)}>Назад</button>
              <button type="button" disabled={!data.has_more} onClick={() => setPage(data.page + 1)}>Далее</button>
            </span>
          </div>
        )}
        <p className="emp-note">Окно принятия — 1 ч, после вызова перерыв 24 ч. Победитель берёт 10–50% казны, победивший нападающий — ещё 3–8 городов с их бизнесами.</p>
      </Panel>

      <Panel title="ИСТОРИЯ ВОЙН">
        {ruler.history.length === 0 ? (
          <p className="emp-note" style={{ textAlign: "center" }}>Войн ещё не было.</p>
        ) : (
          ruler.history.map((h) => {
            const how = h.won === null ? "аннулирована" : h.forfeit ? (h.as_attacker ? "соперник не принял" : "не принял вызов") : "бой";
            const sign = h.won ? "+" : "−";
            return (
              <div key={h.war_id} className="emp-hist">
                {h.as_attacker ? <Swords size={15} /> : <Shield size={15} />}
                <div style={{ flex: 1 }}>
                  {h.as_attacker ? `Напал на ${h.other}` : `${h.other} напал`} —{" "}
                  <span className={h.won ? "win" : "lose"}>{h.won === null ? "без итога" : h.won ? "победа" : "поражение"}</span>
                  <small>{how}{h.cities ? ` · ${sign}${h.cities} гор.` : ""}{h.treasury ? ` · ${sign}${fmt(h.treasury)} казны` : ""}</small>
                </div>
              </div>
            );
          })
        )}
      </Panel>

      {target && (
        <Sheet title={`Война: ${target.name}`} onClose={() => setTarget(null)}>
          <StatRow label="Страна" value={target.country ?? "—"} />
          <StatRow label="Городов" value={target.cities} />
          <StatRow label="Казна" value={fmt(target.treasury)} />
          <p className="emp-note" style={{ margin: "10px 0" }}>Бьётся твой лагерь атаки против его лагеря атаки. После вызова — перерыв 24 ч.</p>
          <button className="btn red block" type="button" disabled={busy} onClick={async () => { if (await run("/empire/war/declare", { target_id: target.user_id })) setTarget(null); }}>
            <Swords size={16} />Объявить войну
          </button>
        </Sheet>
      )}
    </>
  );
}

function SabotageButton({ action, busy, onRun }: { action: SabotageAction; busy: boolean; onRun: (code: string) => void }) {
  const left = useCountdown(action.cooldown_seconds);
  return (
    <button className="btn violet emp-act" type="button" disabled={busy || left > 0} onClick={() => onRun(action.code)}>
      <span>{action.label}</span>
      <span>{left > 0 ? countdown(left) : `${action.chance}%`}</span>
    </button>
  );
}

function SubjectView({ subject, onChanged }: { subject: EmpireSubject; onChanged: () => void }) {
  const { run, busy } = useAction(onChanged);
  return (
    <>
      <Panel title="ТВОЙ ИМПЕРАТОР" tone="gold" badgeMark="♛">
        <div className="row">
          <div className="row" style={{ gap: 10 }}>
            <Crown size={22} color="var(--gold-2)" />
            <div>
              <div style={{ fontSize: 15, fontWeight: 800 }}>
                {subject.emperor} {subject.emperor_username && <span className="muted" style={{ fontSize: 11 }}>@{subject.emperor_username}</span>}
              </div>
              <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>{fmt(subject.emperor_cities)} гор.{subject.emperor_country ? ` · ${subject.emperor_country}` : ""}</div>
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="disp" style={{ fontSize: 18, color: "var(--red-2, #ff8aa0)" }}>{subject.tax_percent}%</div>
            <div className="muted" style={{ fontSize: 10, fontWeight: 700 }}>налог с дохода</div>
          </div>
        </div>
      </Panel>
      <Panel title="САБОТАЖ" tone="violet" badgeMark="?">
        <p className="emp-note" style={{ margin: "0 0 10px" }}>У каждого действия свой перерыв 12 ч. Провал — только перерыв, император не узнает, кто это был.</p>
        {subject.actions.map((a) => (
          <SabotageButton key={a.code} action={a} busy={busy} onRun={(code) => run("/empire/sabotage", { action: code })} />
        ))}
        <p className="emp-note">Статисты — 5% одной его стопки (не больше твоих) · уник не с позиции · казна — 3%, до 100 000 за раз.</p>
      </Panel>
    </>
  );
}

export function EmpirePage() {
  const { data, status, error, reload } = useApi<EmpireData>("/empire");
  const [tab, setTab] = useState<"tax" | "war">("tax");
  const ruler = data?.ruler ?? null;
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Империя" subtitle={data.subtitle} backLabel="Карта" to={ROUTE_MAP} />
          {!ruler && !data.subject && (
            <Panel title="ИМПЕРИЯ"><p className="emp-note" style={{ margin: 0 }}>Над твоим городом нет императора.</p></Panel>
          )}
          {ruler && (
            <>
              <div className="grid-3">
                <div className="chip emp-chip"><span className="muted">Города</span><span className="disp" style={{ color: "var(--cyan-2)" }}>{fmt(ruler.cities)}</span></div>
                <div className="chip emp-chip"><span className="muted">Подданные</span><span className="disp" style={{ color: "var(--violet-2)" }}>{fmt(ruler.players)}</span></div>
                <div className="chip emp-chip"><span className="muted">Казна</span><span className="disp" style={{ color: "var(--gold-2)" }}>{fmt(ruler.treasury)}</span></div>
              </div>
              <div className="seg" role="tablist" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                <button type="button" role="tab" aria-selected={tab === "tax"} className={`pill ${tab === "tax" ? "on" : ""}`} style={{ minHeight: 44 }} onClick={() => setTab("tax")}>Налоги</button>
                <button type="button" role="tab" aria-selected={tab === "war"} className={`pill ${tab === "war" ? "on" : ""}`} style={{ minHeight: 44 }} onClick={() => setTab("war")}>
                  Война{ruler.incoming ? " · !" : ""}
                </button>
              </div>
              {tab === "tax" ? (
                <TaxTab ruler={ruler} min={data.tax_min} max={data.tax_max} onChanged={reload} />
              ) : (
                <WarTab ruler={ruler} onChanged={reload} />
              )}
            </>
          )}
          {data.subject && <SubjectView subject={data.subject} onChanged={reload} />}
        </div>
      )}
    </Screen>
  );
}
