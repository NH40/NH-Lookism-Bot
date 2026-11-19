import { useState } from "react";
import { Panel, Screen } from "../../components/ui";
import { useAction, useApi } from "../../hooks/useApi";
import { Thread, type SupportThread } from "../Support/SupportPage";

// Админка → Поддержка (2026-11-20): очередь обращений, переписка, ответ (уходит игроку пушем), закрытие.
export function SupportSection() {
  const list = useApi<{ waiting: number; items: { id: number; user_id: number; status: string; preview: string }[] }>("/admin/support");
  const [open, setOpen] = useState<number | null>(null);
  return (
    <Screen status={list.status} error={list.error}>
      {list.data && (open === null ? (
        <Panel title={`Ждут ответа: ${list.data.waiting}`}>
          {list.data.items.length === 0 && <div className="adm-hint">Очередь пуста.</div>}
          <div className="adm-list">
            {list.data.items.map((t) => (
              <button key={t.id} type="button" className="adm-item" onClick={() => setOpen(t.id)}>
                <div><b>#{t.id} · игрок {t.user_id}</b><small>{t.preview || "…"}</small></div>
              </button>
            ))}
          </div>
        </Panel>
      ) : (
        <TicketView id={open} onBack={() => { setOpen(null); list.reload(); }} />
      ))}
    </Screen>
  );
}

function TicketView({ id, onBack }: { id: number; onBack: () => void }) {
  const t = useApi<SupportThread>(`/admin/support/${id}`);
  const { run, busy } = useAction(t.reload);
  const [text, setText] = useState("");
  return (
    <Screen status={t.status} error={t.error}>
      {t.data && (
        <Panel title={`Обращение #${id} · игрок ${t.data.user_id}`}>
          <Thread t={t.data} staff />
          <textarea style={{ width: "100%", minHeight: 90, padding: 10, marginTop: 10 }} value={text} onChange={(e) => setText(e.target.value)} placeholder="Ответ игроку" />
          <div className="grid-3" style={{ gap: 6, marginTop: 8 }}>
            <button type="button" className="btn ghost small" onClick={onBack}>Назад</button>
            <button type="button" className="btn ghost small" disabled={busy} onClick={async () => { if (await run(`/admin/support/${id}/close`)) onBack(); }}>Закрыть</button>
            <button type="button" className="btn gold small" disabled={busy || !text.trim()} onClick={async () => { if (await run(`/admin/support/${id}/reply`, { text: text.trim() })) setText(""); }}>Ответить</button>
          </div>
        </Panel>
      )}
    </Screen>
  );
}
