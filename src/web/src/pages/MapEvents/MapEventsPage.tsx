import { Lock } from "lucide-react";
import { imgUrl } from "../../api";
import type { EventCatalogEntry, EventsCatalog } from "../../types";
import { BackHeader, Panel, Screen, countdown } from "../../components/ui";
import { ROUTE_MAP } from "../../constants/constants";
import { useApi } from "../../hooks/useApi";
import "./MapEvents.css";

function EventTile({ e }: { e: EventCatalogEntry }) {
  const src = imgUrl(e.image, 320);
  return (
    <div className={`ev-card ${e.kind === "boss" ? "boss" : ""} ${e.active ? "active" : ""} ${src ? "" : "noart"}`}>
      {src ? (
        <img src={src} alt={e.name} loading="lazy" />
      ) : (
        <div className="ev-noart">
          <Lock size={18} color="#ff9fb0" />
          нужен арт
        </div>
      )}
      {e.active && <span className="ev-live">СЕЙЧАС</span>}
      <div className="ev-cap">
        {e.name}
        <div>{e.active && e.ends_in_seconds ? `ещё ${countdown(e.ends_in_seconds)}` : e.subtitle}</div>
      </div>
    </div>
  );
}

function Group({ title, tone, items }: { title: string; tone?: "red"; items: EventCatalogEntry[] }) {
  return (
    <Panel title={title} tone={tone} badgeMark={tone === "red" ? "!" : "i"}>
      <div className="grid-3">
        {items.map((e) => (
          <EventTile key={`${e.kind}-${e.code}`} e={e} />
        ))}
      </div>
    </Panel>
  );
}

export function MapEventsPage() {
  const { data, status, error } = useApi<EventsCatalog>("/map/events-catalog");
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="События карты" subtitle="кто может появиться" backLabel="Карта" to={ROUTE_MAP} />
          <Group title="Боссы" tone="red" items={data.bosses} />
          <Group title="Учителя техник" items={data.teachers} />
          <Group title="Учителя школ" items={data.schools} />
          <div className="muted ev-note">
            Клановые боссы и учителя — те же персонажи, их видят только участники клана. Пунктир — арт нужно подготовить.
          </div>
        </div>
      )}
    </Screen>
  );
}
