import { Bookmark, BookmarkCheck, Eye, RefreshCw, Search } from "lucide-react";
import { useState } from "react";
import { apiGet, apiPost, ApiError } from "../../api";
import type { IntelData, IntelLog, ScoutReport, ScoutRow } from "../../types";
import { BackHeader, Panel, Screen, useToast } from "../../components/ui";
import { ROUTE_MORE } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import "./Intel.css";

// Разведка — отдельный этап (как в боте): «Разведать» сохраняет отчёт, его можно открыть в любой
// момент. Что видно — решают навыки карты на позиции Разведки; Безопасность цели прячет поля
// (выше уровень — точно, равный — вилка, ниже — «скрыто»). Метки и саботаж помеченного — тут же.

const SEEN_LABEL: Record<string, string> = { exact: "точно", range: "вилка", hidden: "скрыто" };

function when(at: string): string {
  return new Date(at).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function Logs({ entries }: { entries: IntelLog[] }) {
  if (!entries.length) return <p className="muted intel-note">Записей пока нет.</p>;
  return (
    <div className="intel-logs">
      {entries.map((e, i) => (
        <div key={i}><span className="muted">{when(e.at)}</span> · {e.text}</div>
      ))}
    </div>
  );
}

export function IntelPage() {
  const toast = useToast();
  const { data, status, error, reload } = useApi<IntelData>("/intel");
  const reports = useApi<ScoutRow[]>("/intel/reports");
  const [nick, setNick] = useState("");
  const [report, setReport] = useState<ScoutReport | null>(null);
  const [busyScout, setBusyScout] = useState(false);

  const refreshAll = async () => {
    await Promise.all([reload(), reports.reload()]);
  };
  const { run, busy } = useAction(async () => {
    await refreshAll();
    if (report) setReport(await apiGet<ScoutReport>(`/intel/scout/${report.target_id}`));
  });

  const doScout = async (body: { username?: string; target_id?: number }) => {
    if (busyScout) return;
    setBusyScout(true);
    try {
      const r = await apiPost<ScoutReport>("/intel/scout", body);
      setReport(r);
      if (r.trap_lost) toast(`Ловушка цели: потеряно ${r.trap_lost} статистов`, "err");
      await reports.reload();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : String(err), "err");
    } finally {
      setBusyScout(false);
    }
  };
  const openSaved = async (targetId: number) => {
    try {
      setReport(await apiGet<ScoutReport>(`/intel/scout/${targetId}`));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : String(err), "err");
    }
  };
  const access = data && (data.fields || data.marks_limit);

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Разведка" subtitle={data.fields ? `видит полей: ${data.fields}` : undefined} backLabel="Ещё" to={ROUTE_MORE} />
          {!access ? (
            <Panel title="НЕТ РАЗВЕДЧИКА" tone="violet" badgeMark="?">
              <p className="muted intel-note" style={{ margin: 0 }}>
                Поставь уника на позицию «Разведка» — разведка открывается её навыками: число статистов, мощь лагерей,
                ранги, кто на позициях, родословная, кошелёк, последние бои и другое. Ещё её дают гении хакинга и наблюдения.
              </p>
            </Panel>
          ) : (
            <>
              <div className="row" style={{ gap: 8 }}>
                <input className="intel-input" placeholder="@ник игрока" value={nick} onChange={(e) => setNick(e.currentTarget.value.replace(/\s/g, ""))} onKeyDown={(e) => e.key === "Enter" && nick && doScout({ username: nick })} />
                <button className="btn small" type="button" disabled={busyScout || !nick} onClick={() => doScout({ username: nick })}><Search size={14} />Разведать</button>
              </div>
              <p className="muted intel-note" style={{ marginTop: 0 }}>Без перерыва. Отчёт сохраняется — его можно открыть перед атакой в любой момент.</p>

              {report && (
                <Panel title="ОТЧЁТ" tone="violet" badgeMark="?">
                  <div className="row">
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 15, fontWeight: 800 }}>{report.name}</div>
                      <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>разведано {report.ago}</div>
                    </div>
                    <button className="btn small ghost" type="button" disabled={busyScout} onClick={() => doScout({ target_id: report.target_id })}><RefreshCw size={14} />Снова</button>
                  </div>
                  <div className="scout-fields">
                    {report.fields.map((f) => (
                      <div key={f.field} className={`scout-field s-${f.seen}`}>
                        <span className="sf-label">{f.label}</span>
                        <span className="sf-value">{f.value}</span>
                        <span className="sf-seen">{SEEN_LABEL[f.seen]}</span>
                      </div>
                    ))}
                  </div>
                  {report.can_mark && (
                    <button className="btn small gold block" type="button" style={{ marginTop: 10 }} disabled={busy} onClick={() => run("/intel/mark", { target_id: report.target_id })}>
                      {report.marked ? <BookmarkCheck size={14} /> : <Bookmark size={14} />}
                      {report.marked ? "Снять метку" : "Поставить метку"}
                    </button>
                  )}
                  {report.can_sabotage && (
                    <>
                      <div className="intel-sub">Саботаж помеченного</div>
                      {report.sabotage_actions.map(([code, label, chance]) => (
                        <button key={code} className="btn violet block intel-act" type="button" disabled={busy} onClick={() => run("/empire/sabotage", { action: code, target_id: report.target_id })}>
                          <span>{label}</span>
                          <span>{chance}%</span>
                        </button>
                      ))}
                    </>
                  )}
                </Panel>
              )}

              <Panel title="МОИ ОТЧЁТЫ">
                {!reports.data || reports.data.length === 0 ? (
                  <p className="muted intel-note" style={{ margin: 0 }}>Отчётов пока нет — разведай кого-нибудь.</p>
                ) : (
                  reports.data.map((r) => (
                    <button key={r.target_id} type="button" className="intel-row" onClick={() => openSaved(r.target_id)}>
                      <Eye size={16} />
                      <span className="grow">{r.name}</span>
                      <small>{r.ago}</small>
                    </button>
                  ))
                )}
              </Panel>

              {data.marks_limit > 0 && (
                <Panel title={`МЕТКИ ${data.marks.length}/${data.marks_limit}`} tone="gold">
                  {data.marks.length === 0 ? (
                    <p className="muted intel-note" style={{ margin: 0 }}>Меток нет — поставь её из отчёта, и здесь появятся свежие действия игрока.</p>
                  ) : (
                    data.marks.map((m) => (
                      <div key={m.target_id} className="intel-mark">
                        <b><Eye size={14} /> {m.name}</b>
                        {m.hidden ? <p className="muted intel-note">Скрыт.</p> : <Logs entries={m.entries} />}
                      </div>
                    ))
                  )}
                </Panel>
              )}
            </>
          )}
        </div>
      )}
    </Screen>
  );
}
