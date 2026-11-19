import { useState } from "react";
import { BackHeader, Panel, Screen } from "../../components/ui";
import { ROUTE_MORE } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";

// Поддержка (2026-11-20): переписка игрока с поддержкой; ответ приходит и пушем в бота.
export interface SupportThread { id: number; status: string; user_id: number; messages: { staff: boolean; text: string; at: string }[] }
const STATUS: Record<string, string> = { open: "ждёт ответа", answered: "есть ответ", closed: "закрыто" };

export function Thread({ t, staff }: { t: SupportThread; staff?: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {t.messages.map((m, i) => (
        <div key={i} style={{ alignSelf: m.staff === !staff ? "flex-start" : "flex-end", maxWidth: "88%", padding: "8px 10px", borderRadius: 10,
          background: m.staff ? "rgba(79,216,255,0.12)" : "rgba(255,191,60,0.12)", fontSize: 13, fontWeight: 600, whiteSpace: "pre-line" }}>
          <small className="muted" style={{ display: "block", fontSize: 10.5 }}>{m.staff ? "🛡 Поддержка" : staff ? "👤 Игрок" : "👤 Ты"}</small>
          {m.text}
        </div>
      ))}
    </div>
  );
}

export function SupportPage() {
  const { data, status, error, reload } = useApi<{ thread: SupportThread | null; max: number }>("/support");
  const { run, busy } = useAction(reload);
  const [text, setText] = useState("");
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Поддержка" backLabel="Ещё" to={ROUTE_MORE} subtitle={data.thread ? `обращение #${data.thread.id} · ${STATUS[data.thread.status]}` : undefined} />
          {data.thread && <Panel title="Переписка"><Thread t={data.thread} /></Panel>}
          <Panel title={data.thread && data.thread.status !== "closed" ? "Дописать" : "Новое обращение"}>
            <textarea style={{ width: "100%", minHeight: 110, padding: 10 }} maxLength={data.max} value={text} onChange={(e) => setText(e.target.value)}
              placeholder="Опиши проблему — ответят модераторы или админы" />
            <button type="button" className="btn gold block" style={{ marginTop: 8 }} disabled={busy || !text.trim()}
              onClick={async () => { if (await run("/support", { text: text.trim() })) setText(""); }}>Отправить</button>
          </Panel>
        </div>
      )}
    </Screen>
  );
}
