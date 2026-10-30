import { Gem, RefreshCw, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../../api";
import type { DonateData } from "../../types";
import { BackHeader, Panel, Screen, Spinner, fmt, useToast } from "../../components/ui";
import { ROUTE_MARKET, ROUTE_MORE } from "../../constants";
import { useApi } from "../../hooks/useApi";
import { getWebApp } from "../../telegram";

type Method = "sbp" | "card";

interface SbpPayment {
  id: number;
  url: string;
  status: "pending" | "succeeded" | "canceled" | "expired";
}

const SBP_POLL_MS = 4000;

export function DonatePage() {
  const { data, status, error, reload } = useApi<DonateData>("/donate");
  const toast = useToast();
  const navigate = useNavigate();
  const [custom, setCustom] = useState("");
  const [busy, setBusy] = useState(false);
  const [method, setMethod] = useState<Method>("sbp");
  const [sbp, setSbp] = useState<SbpPayment | null>(null);
  const [sbpAmount, setSbpAmount] = useState(0);
  const timer = useRef<number | null>(null);

  // Выбранный способ должен быть доступен: если СБП не подключена — карта, и наоборот.
  useEffect(() => {
    if (!data) return;
    if (method === "sbp" && !data.sbp_enabled && data.card_enabled) setMethod("card");
    if (method === "card" && !data.card_enabled && data.sbp_enabled) setMethod("sbp");
  }, [data, method]);

  // Пока счёт СБП открыт — опрашиваем его статус (зачисляет вебхук / фоновая проверка бота).
  useEffect(() => {
    if (!sbp || sbp.status !== "pending") return;
    timer.current = window.setInterval(async () => {
      try {
        const fresh = await apiGet<SbpPayment>(`/donate/sbp/${sbp.id}`);
        if (fresh.status !== "pending") setSbp(fresh);
      } catch {
        /* сеть моргнула — следующий опрос */
      }
    }, SBP_POLL_MS);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [sbp]);

  useEffect(() => {
    if (sbp?.status === "succeeded") {
      toast("Оплата получена! Коины зачислены.", "ok");
      void reload();
    }
  }, [sbp?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  function openLink(url: string) {
    const webApp = getWebApp();
    if (webApp?.openLink) webApp.openLink(url);
    else window.open(url, "_blank");
  }

  async function payCard(amount: number) {
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
  }

  async function paySbp(amount: number) {
    const created = await apiPost<SbpPayment>("/donate/sbp", { amount });
    setSbp(created);
    setSbpAmount(amount);
    openLink(created.url);
  }

  async function pay(amount: number) {
    if (!data || busy) return;
    if (!Number.isInteger(amount) || amount < data.min_rub || amount > data.max_rub) {
      toast(`Сумма — от ${data.min_rub} до ${fmt(data.max_rub)} ₽.`, "err");
      return;
    }
    setBusy(true);
    try {
      await (method === "sbp" ? paySbp(amount) : payCard(amount));
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "err");
    } finally {
      setBusy(false);
    }
  }

  async function checkSbp() {
    if (!sbp || busy) return;
    setBusy(true);
    try {
      const fresh = await apiPost<SbpPayment>(`/donate/sbp/${sbp.id}/check`);
      setSbp(fresh);
      if (fresh.status === "pending") toast("Оплата ещё не поступила. Если уже оплатил — подожди минуту.", "err");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "err");
    } finally {
      setBusy(false);
    }
  }

  const canPay = data ? (method === "sbp" ? data.sbp_enabled : data.card_enabled) : false;

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

          {sbp && (
            <Panel title="Оплата по СБП" tone="violet">
              {sbp.status === "pending" && (
                <>
                  <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>
                    <Zap size={15} style={{ verticalAlign: "-2px" }} /> {fmt(sbpAmount)} ₽ — оплати в приложении банка.
                  </div>
                  <div className="muted" style={{ fontSize: 12, fontWeight: 600, marginBottom: 10 }}>
                    Коины придут сами сразу после оплаты. Окно банка не открылось — нажми «Открыть оплату».
                  </div>
                  <div className="grid-2">
                    <button className="btn gold" onClick={() => openLink(sbp.url)}>
                      Открыть оплату
                    </button>
                    <button className="btn" disabled={busy} onClick={checkSbp}>
                      {busy ? <Spinner /> : <><RefreshCw size={14} /> Я оплатил</>}
                    </button>
                  </div>
                </>
              )}
              {sbp.status === "succeeded" && (
                <div style={{ fontSize: 14, fontWeight: 700 }}>✅ Оплачено — зачислено {fmt(sbpAmount)} 💎</div>
              )}
              {(sbp.status === "canceled" || sbp.status === "expired") && (
                <div className="muted" style={{ fontSize: 13, fontWeight: 600 }}>
                  Платёж отменён или истёк. Выбери сумму ещё раз, чтобы создать новый.
                </div>
              )}
              {sbp.status !== "pending" && (
                <button className="btn small" style={{ marginTop: 10 }} onClick={() => setSbp(null)}>
                  Закрыть
                </button>
              )}
            </Panel>
          )}

          <Panel title="Пополнить" tone="gold">
            {!data.payments_enabled && (
              <div className="muted" style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>
                Оплата пока не подключена.
              </div>
            )}
            {data.sbp_enabled && data.card_enabled && (
              <div className="seg" style={{ gridTemplateColumns: "1fr 1fr", marginBottom: 12 }}>
                <button type="button" className={`pill ${method === "sbp" ? "on" : ""}`} onClick={() => setMethod("sbp")}>
                  ⚡ СБП
                </button>
                <button type="button" className={`pill ${method === "card" ? "on" : ""}`} onClick={() => setMethod("card")}>
                  💳 Картой
                </button>
              </div>
            )}
            <div className="grid-3">
              {data.presets.map((rub) => (
                <button key={rub} className={`btn gold ${canPay ? "" : "off"}`} disabled={busy || !canPay} onClick={() => pay(rub)}>
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
              <button className={`btn ${canPay ? "" : "off"}`} disabled={busy || !canPay || !custom} onClick={() => pay(Number(custom))}>
                {busy ? <Spinner /> : "Оплатить"}
              </button>
            </div>
          </Panel>
        </div>
      )}
    </Screen>
  );
}
