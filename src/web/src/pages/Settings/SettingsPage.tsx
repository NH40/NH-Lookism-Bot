import { Bell, BellOff } from "lucide-react";
import type { SettingsData } from "../../types";
import { BackHeader, Panel, Screen } from "../../components/ui";
import { ROUTE_MORE } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import "./Settings.css";

export function SettingsPage() {
  const { data, status, error, reload } = useApi<SettingsData>("/settings");
  const { run, busy } = useAction(reload);
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Настройки" to={ROUTE_MORE} />
          <Panel title="Уведомления">
            <div className="muted" style={{ fontSize: 12, fontWeight: 600, marginBottom: 10 }}>
              Выключенное просто не приходит в бот — сама механика работает как обычно.
            </div>
            <div className="grid-2" style={{ marginBottom: 6 }}>
              <button className="btn green small" disabled={busy} onClick={() => run("/settings/all", { enabled: true })}>
                <Bell size={14} /> Включить все
              </button>
              <button className="btn ghost small" disabled={busy} onClick={() => run("/settings/all", { enabled: false })}>
                <BellOff size={14} /> Выключить все
              </button>
            </div>
            {data.categories.map((c) => (
              <button key={c.code} type="button" className="set-row" disabled={busy} onClick={() => run("/settings/toggle", { category: c.code })}>
                <span>{c.label}</span>
                <span className={`set-switch ${c.enabled ? "on" : ""}`} aria-checked={c.enabled} role="switch">
                  <i />
                </span>
              </button>
            ))}
          </Panel>
        </div>
      )}
    </Screen>
  );
}
