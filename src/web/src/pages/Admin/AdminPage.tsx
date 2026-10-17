// Админ-панель: главная (разделы по роли) и экран раздела. Права проверяет сервер на каждом
// запросе — здесь только не показываем то, что роли всё равно недоступно.
import {
  BarChart3,
  Beaker,
  Bomb,
  CalendarRange,
  Crown,
  Link2,
  Map as MapIcon,
  Megaphone,
  ScrollText,
  Settings2,
  Shield,
  Sparkles,
  Ticket,
  User,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiGet } from "../../api";
import { BackHeader, Panel, Screen, useToast } from "../../components/ui";
import { ROUTE_ADMIN, ROUTE_MORE, adminPlayerPath, adminSectionPath } from "../../constants";
import type { AdminMeta } from "../../types";
import { TextInput, useAdminMeta } from "./AdminKit";
import { ConfigSection, LogsSection, PatchSection, RolesSection, StatsSection, SystemSection } from "./SectionsCore";
import { ClansSection, EventsSection, MassSection, PromoSection, ReferralSection, SeasonSection, WorldSection } from "./SectionsOps";
import "./Admin.css";

const ICONS: Record<string, ReactNode> = {
  players: <User size={18} />,
  mass: <Megaphone size={18} />,
  promo: <Ticket size={18} />,
  stats: <BarChart3 size={18} />,
  logs: <ScrollText size={18} />,
  world: <MapIcon size={18} />,
  events: <Sparkles size={18} />,
  clans: <Shield size={18} />,
  season: <CalendarRange size={18} />,
  referral: <Link2 size={18} />,
  roles: <Crown size={18} />,
  patch: <Bomb size={18} />,
  config: <Settings2 size={18} />,
  system: <Beaker size={18} />,
};

const HINTS: Record<string, string> = {
  players: "поиск, выдача, развитие, наказания",
  mass: "рассылка и массовая выдача",
  promo: "создать, выключить, удалить",
  stats: "игроки, донат, экономика, сервер",
  logs: "аудит, платежи, покупки",
  world: "города, районы, императоры",
  events: "боссы и учителя на карте",
  clans: "земли, казна, владелец",
  season: "пасс и задания игрока",
  referral: "кампании и ссылки",
  roles: "сотрудники админки",
  patch: "сброс прогресса и вайп",
  config: "числа без перезапуска",
  system: "бета-режим и техрежим",
};

export function AdminPage() {
  const { data, status, error } = useAdminMeta();
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title="Админ-панель" subtitle={data.role_name} to={ROUTE_MORE} />
          <div className="grid-2" style={{ gap: 10 }}>
            {data.sections.map((s) => (
              <Link key={s.code} className="tile" to={adminSectionPath(s.code)}>
                <div className="ico-box">{ICONS[s.code]}</div>
                <b>{s.title}</b>
                <small>{HINTS[s.code] ?? ""}</small>
              </Link>
            ))}
          </div>
        </div>
      )}
    </Screen>
  );
}

export function AdminSectionPage() {
  const { section = "" } = useParams();
  const { data, status, error } = useAdminMeta();
  const title = data?.sections.find((s) => s.code === section)?.title ?? "Раздел";
  return (
    <Screen status={status} error={error}>
      {data && (
        <div className="page">
          <BackHeader title={title} to={ROUTE_ADMIN} />
          {data.sections.some((s) => s.code === section) ? <SectionBody section={section} meta={data} /> : <Panel>Нет доступа к разделу.</Panel>}
        </div>
      )}
    </Screen>
  );
}

function SectionBody({ section, meta }: { section: string; meta: AdminMeta }) {
  switch (section) {
    case "players":
      return <PlayersSection />;
    case "mass":
      return <MassSection meta={meta} />;
    case "promo":
      return <PromoSection />;
    case "stats":
      return <StatsSection />;
    case "logs":
      return <LogsSection />;
    case "world":
      return <WorldSection />;
    case "events":
      return <EventsSection meta={meta} />;
    case "clans":
      return <ClansSection />;
    case "season":
      return <SeasonSection />;
    case "referral":
      return <ReferralSection />;
    case "roles":
      return <RolesSection meta={meta} />;
    case "patch":
      return <PatchSection />;
    case "config":
      return <ConfigSection meta={meta} />;
    case "system":
      return <SystemSection />;
    default:
      return <Panel>Неизвестный раздел.</Panel>;
  }
}

/** Поиск игрока по @нику или id → карточка. */
function PlayersSection() {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();
  const find = async () => {
    if (!query.trim()) return;
    setBusy(true);
    try {
      const r = await apiGet<{ id: number }>(`/admin/players/find?q=${encodeURIComponent(query.trim())}`);
      navigate(adminPlayerPath(r.id));
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "err");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel title="Поиск игрока">
      <div className="adm-hint">@ник или Telegram id игрока.</div>
      <form
        className="adm-inline"
        onSubmit={(e) => {
          e.preventDefault();
          void find();
        }}
      >
        <TextInput value={query} onChange={setQuery} placeholder="@nick или 123456789" />
        <button type="submit" className="btn small" disabled={busy || !query.trim()}>
          Найти
        </button>
      </form>
    </Panel>
  );
}
