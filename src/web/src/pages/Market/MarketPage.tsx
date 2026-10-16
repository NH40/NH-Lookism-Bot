import { Gem, Sparkles, UserPlus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { MarketData, MarketItem } from "../../types";
import { BackHeader, Panel, Screen, fmt } from "../../components/ui";
import { ROUTE_DONATE, ROUTE_MORE, ROUTE_QUESTS } from "../../constants";
import { useAction, useApi } from "../../hooks/useApi";
import "./Market.css";

/** Чёрный рынок: второе тело, гении, пути и техники с постоянными уровнями (services/donate). */
export function MarketPage() {
  const { data, status, error, reload } = useApi<MarketData>("/donate/market");
  const { run, busy } = useAction(reload);
  const [kind, setKind] = useState<string | null>(null);
  const navigate = useNavigate();

  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Чёрный рынок" subtitle={`баланс: ${fmt(data.balance)} донат-коинов`} to={ROUTE_MORE} />

          <Panel title="Второе тело" badgeMark="2" tone="violet">
            {data.second_body_owned ? (
              <div className="mk-text">Куплено. Второй путь и вторая родословная — на экране развития.</div>
            ) : (
              <>
                <div className="mk-text">
                  Одно на аккаунт: <b>два активных пути</b> сразу и <b>вторая родословная</b> на выбор — бафы обоих работают.
                </div>
                <button className="btn violet block" type="button" disabled={busy} onClick={() => void run("/donate/market/body")}>
                  <UserPlus size={18} /> Купить за {fmt(data.second_body_price)} <Gem size={15} />
                </button>
              </>
            )}
          </Panel>

          <div className="seg" style={{ gridTemplateColumns: `repeat(${data.kinds.length}, minmax(0, 1fr))` }}>
            {data.kinds.map((k) => (
              <button key={k.kind} type="button" className={`pill ${(kind ?? data.kinds[0]?.kind) === k.kind ? "on" : ""}`} onClick={() => setKind(k.kind)}>
                {k.label}
              </button>
            ))}
          </div>

          {data.kinds
            .filter((k) => k.kind === (kind ?? data.kinds[0]?.kind))
            .map((k) => (
              <Panel key={k.kind} title={k.label}>
                <div className="mk-text muted">{k.hint}</div>
                <div className="mk-list">
                  {k.items.map((item) => (
                    <MarketRow key={item.code} item={item} maxLevel={data.max_level} busy={busy}
                      onBuy={() => void run(item.level ? "/donate/market/level" : "/donate/market/unlock", { kind: k.kind, code: item.code })} />
                  ))}
                </div>
              </Panel>
            ))}

          <Panel title="Battle Pass" tone="gold">
            <div className="row">
              <div className="mk-text" style={{ margin: 0 }}>
                {data.battle_pass_premium ? "Платная ветка открыта до конца сезона." : `Платная ветка сезона — ${fmt(data.battle_pass_price)} донат-коинов`}
              </div>
              <button className="btn gold small" type="button" onClick={() => navigate(ROUTE_QUESTS)}>
                <Sparkles size={15} /> К пассу
              </button>
            </div>
          </Panel>

          <button className="btn ghost block" type="button" onClick={() => navigate(ROUTE_DONATE)}>
            <Gem size={18} /> Пополнить донат-коины
          </button>
        </div>
      )}
    </Screen>
  );
}

function MarketRow({ item, maxLevel, busy, onBuy }: { item: MarketItem; maxLevel: number; busy: boolean; onBuy: () => void }) {
  const owned = item.level > 0;
  return (
    <div className={`mk-row ${owned ? "owned" : ""}`}>
      <div className="mk-head">
        <b>{item.name}</b>
        <span className="disp mk-level">{owned ? `${item.level}/${maxLevel}` : "закрыто"}</span>
      </div>
      <div className="mk-seg">
        {Array.from({ length: maxLevel }, (_, i) => (
          <span key={i} className={i < item.level ? "on" : ""} />
        ))}
      </div>
      {item.next_price !== null ? (
        <button className={`btn small ${owned ? "violet" : ""}`} type="button" disabled={busy} onClick={onBuy}>
          {owned ? `Ур. ${item.level + 1} за ${fmt(item.next_price)}` : `Открыть за ${fmt(item.next_price)}`} <Gem size={14} />
        </button>
      ) : (
        <div className="mk-max">Максимальный уровень</div>
      )}
    </div>
  );
}
