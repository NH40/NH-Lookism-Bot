import { ClipboardList, Map, Settings, ShoppingBag, Sparkles, User, Users } from "lucide-react";
import { NavLink } from "react-router-dom";
import {
  ROUTE_CLANS,
  ROUTE_DEVELOPMENT,
  ROUTE_MAP,
  ROUTE_PROFILE,
  ROUTE_QUESTS,
  ROUTE_SETTINGS,
  ROUTE_SHOP,
} from "../constants";
import type { NavTab } from "../types";

// 7 вкладок нижней навигации — Профиль/Карта/Развитие/Магазин/Кланы/Задания/Настройки
// (см. CLAUDE.md, "LookismBattlePlanet 2.0.0"). Только Профиль сейчас ведёт на реальный
// экран — остальные 6 рендерят честную заглушку "в разработке" (см. PlaceholderPage).
const TABS: NavTab[] = [
  { path: ROUTE_PROFILE, label: "Профиль", Icon: User },
  { path: ROUTE_MAP, label: "Карта", Icon: Map },
  { path: ROUTE_DEVELOPMENT, label: "Развитие", Icon: Sparkles },
  { path: ROUTE_SHOP, label: "Магазин", Icon: ShoppingBag },
  { path: ROUTE_CLANS, label: "Кланы", Icon: Users },
  { path: ROUTE_QUESTS, label: "Задания", Icon: ClipboardList },
  { path: ROUTE_SETTINGS, label: "Настройки", Icon: Settings },
];

export function NavTabs() {
  return (
    <nav className="nav-tabs">
      {TABS.map((tab) => (
        <NavLink
          key={tab.path}
          to={tab.path}
          end={tab.path === ROUTE_PROFILE}
          className={({ isActive }) => (isActive ? "nav-tab active" : "nav-tab")}
        >
          <tab.Icon size={18} />
          <span>{tab.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
