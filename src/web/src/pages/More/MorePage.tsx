import { BookOpen, Briefcase, Dices, Eye, Gem, Gift, Repeat, Settings, ShoppingBag, Trophy, Users, VenetianMask } from "lucide-react";
import { useState } from "react";
import { Sheet } from "../../components/Sheet";
import { useAction } from "../../hooks/useApi";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { MoreData } from "../../types";
import { Panel, Screen, fmt } from "../../components/ui";
import { ROUTE_BUSINESS, ROUTE_CASINO, ROUTE_CLAN, ROUTE_DONATE, ROUTE_EXCHANGE, ROUTE_GANG, ROUTE_GUIDE, ROUTE_INTEL, ROUTE_MARKET, ROUTE_SETTINGS, ROUTE_SHOP, ROUTE_TOP } from "../../constants";
import { useApi } from "../../hooks/useApi";
import "./More.css";

export function MorePage() {
  const { data, status, error } = useApi<MoreData>("/more");
  return (
    <Screen status={status} error={error}>
      {data && <MoreView d={data} />}
    </Screen>
  );
}

function MoreView({ d }: { d: MoreData }) {
  const tile = (icon: ReactNode, title: string, hint: string, to: string, tone = "") => (
    <Link className={`tile ${tone}`} to={to}>
      <div className="ico-box">{icon}</div>
      <b>{title}</b>
      <small>{hint}</small>
    </Link>
  );
  const c = d.clan;
  const [promoOpen, setPromoOpen] = useState(false);
  const [code, setCode] = useState("");
  const { run, busy } = useAction();

  return (
    <div className="page">
      <Link to={ROUTE_CLAN} style={{ textDecoration: "none", color: "inherit" }}>
        <Panel title="Клан">
          {c ? (
            <div className="row">
              <div style={{ minWidth: 0 }}>
                <div className="disp more-clan-name">{c.name}</div>
                <div className="muted more-clan-sub">
                  {c.members}/{c.max_members} участников · ур. клана {c.donate_level}/{c.max_donate_level} · {c.lands} земель
                </div>
              </div>
              <div className="disp more-clan-power">
                {fmt(c.power)}
                <small>мощь роты</small>
              </div>
            </div>
          ) : (
            <div className="muted" style={{ fontSize: 13, fontWeight: 600 }}>
              Ты не состоишь в клане. Вступить или создать клан можно в боте.
            </div>
          )}
        </Panel>
      </Link>

      <div className="grid-2" style={{ gap: 10 }}>
        {tile(<ShoppingBag size={18} />, "Магазин", "контракты, зелья, ячейки", ROUTE_SHOP)}
        {tile(<Users size={18} />, "Банда и армия", "статисты, уники, лагеря", ROUTE_GANG)}
        {tile(<VenetianMask size={18} />, "Чёрный рынок", "второе тело, пути, техники", ROUTE_MARKET, "violet")}
        {tile(<Gem size={18} />, "Донат", `баланс ${fmt(d.donate_balance)} · пополнить`, ROUTE_DONATE, "gold")}
        {tile(<Trophy size={18} />, "Топ", "игроки, кланы, награды сезона", ROUTE_TOP, "gold")}
        {tile(<Repeat size={18} />, "Биржа", "лоты, аукцион, обмен", ROUTE_EXCHANGE)}
        {tile(<Dices size={18} />, "Казино", "слоты, блэкджек, покер", ROUTE_CASINO)}
        {tile(
          <Briefcase size={18} />,
          "Бизнес",
          d.income_pending > 0 ? `доход ${fmt(d.income_per_minute)}/мин · забрать ${fmt(d.income_pending)}` : `доход ${fmt(d.income_per_minute)}/мин`,
          ROUTE_BUSINESS,
        )}
        {tile(<Eye size={18} />, "Разведка", "отчёты и метки", ROUTE_INTEL, "violet")}
        {tile(<BookOpen size={18} />, "Гайд", "всё об игре по разделам", ROUTE_GUIDE)}
        <button type="button" className="tile gold" style={{ font: "inherit", textAlign: "left" }} onClick={() => setPromoOpen(true)}>
          <div className="ico-box"><Gift size={18} /></div>
          <b>Промокод</b>
          <small>ввести код</small>
        </button>
        {tile(<Settings size={18} />, "Настройки", "уведомления", ROUTE_SETTINGS)}
      </div>
      {promoOpen && (
        <Sheet title="Промокод" onClose={() => setPromoOpen(false)}>
          <input className="promo-input" autoFocus placeholder="Код" value={code} onChange={(e) => setCode(e.currentTarget.value.replace(/\s/g, ""))} />
          <button className="btn gold block" type="button" style={{ marginTop: 10 }} disabled={busy || !code}
            onClick={async () => { if (await run("/promo", { code })) { setCode(""); setPromoOpen(false); } }}>
            Активировать
          </button>
        </Sheet>
      )}
    </div>
  );
}
