import { Gem } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiPost } from "../../api";
import type { DonateData } from "../../types";
import { BackHeader, Panel, Screen, Spinner, fmt, useToast } from "../../components/ui";
import { ROUTE_MARKET, ROUTE_MORE } from "../../constants";
import { useApi } from "../../hooks/useApi";
import { getWebApp } from "../../telegram";

export function DonatePage() {
  const { data, status, error, reload } = useApi<DonateData>("/donate");
  const toast = useToast();
  const navigate = useNavigate();
  const [custom, setCustom] = useState("");
  const [busy, setBusy] = useState(false);

  async function pay(amount: number) {
    if (!data || busy) return;
    if (!Number.isInteger(amount) || amount < data.min_rub || amount > data.max_rub) {
      toast(`Сумма — от ${data.min_rub} до ${fmt(data.max_rub)} ₽.`, "err");
      return;
    }
    setBusy(true);
    try {
      const { link } = await apiPost<{ link: string }>("/donate/invoice", { amount });
      const webApp = getWebApp();
      if (!webApp?.openInvoice) {
        toast("Оплата доступна только внутри Telegram.", "err");
        return;
      }
      webApp.openInvoice(link, (result) => {
        if (result === "paid") {
          toast("Оплата прошла! Коины скоро появятся на балансе.", "ok");
          // Зачисление делает бот по successful_payment — даём ему секунду и обновляем баланс.
          setTimeout(() => void reload(), 1500);
        } else if (result === "failed") {
          toast("Оплата не удалась.", "err");
        }
      });
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "err");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Донат" to={ROUTE_MORE} />
          <Panel title="Баланс" tone="violet">
            <div className="row">
              <div className="disp" style={{ fontSize: 28, fontWeight: 800, display: "flex", alignItems: "center", gap: 8 }}>
                <Gem size={26} color="#a78bfa" />
                {data.balance.toLocaleString("ru-RU")}
              </div>
              <button className="btn violet small" onClick={() => navigate(ROUTE_MARKET)}>
                Чёрный рынок
              </button>
            </div>
            <div className="muted" style={{ fontSize: 12, fontWeight: 600, marginTop: 6 }}>
              1 ₽ = 1 донат-коин. Донат ускоряет развитие, но не даёт боевой силы.
            </div>
          </Panel>
          <Panel title="Пополнить" tone="gold">
            {!data.payments_enabled && (
              <div className="muted" style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>
                Оплата пока не подключена.
              </div>
            )}
            <div className="grid-3">
              {data.presets.map((rub) => (
                <button key={rub} className={`btn gold ${data.payments_enabled ? "" : "off"}`} disabled={busy || !data.payments_enabled} onClick={() => pay(rub)}>
                  {fmt(rub)} ₽
                </button>
              ))}
            </div>
            <div className="section-title" style={{ margin: "14px 2px 8px" }}>
              Своя сумма
            </div>
            <div className="row">
              <input
                inputMode="numeric"
                placeholder={`${data.min_rub} – ${fmt(data.max_rub)}`}
                value={custom}
                onChange={(e) => setCustom(e.currentTarget.value.replace(/\D/g, ""))}
                style={{ flex: 1, minWidth: 0, minHeight: 44, borderRadius: 10, border: "1px solid var(--line-soft)", background: "var(--card)", color: "var(--text)", padding: "0 12px", fontSize: 15, fontWeight: 700 }}
              />
              <button className={`btn ${data.payments_enabled ? "" : "off"}`} disabled={busy || !data.payments_enabled || !custom} onClick={() => pay(Number(custom))}>
                {busy ? <Spinner /> : "Оплатить"}
              </button>
            </div>
          </Panel>
        </div>
      )}
    </Screen>
  );
}
