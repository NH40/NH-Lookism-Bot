import { ClipboardList, Ellipsis, Map, Sparkles, User } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { ROUTE_DEVELOPMENT, ROUTE_MAP, ROUTE_MORE, ROUTE_PROFILE, ROUTE_QUESTS } from "../constants";

// 5 вкладок + «Ещё» (утверждено пользователем 2026-10-09). Вложенные экраны (банда, уники,
// тренировки, магазин…) подсвечивают свою родительскую вкладку.
const TABS = [
  { path: ROUTE_PROFILE, label: "Профиль", Icon: User },
  { path: ROUTE_MAP, label: "Карта", Icon: Map },
  { path: ROUTE_DEVELOPMENT, label: "Развитие", Icon: Sparkles },
  { path: ROUTE_QUESTS, label: "Задания", Icon: ClipboardList },
  { path: ROUTE_MORE, label: "Ещё", Icon: Ellipsis },
];

export function NavTabs() {
  const { pathname } = useLocation();
  return (
    <nav className="nav" aria-label="Разделы">
      {TABS.map(({ path, label, Icon }) => {
        const on = path === ROUTE_PROFILE ? pathname === path : pathname.startsWith(path);
        return (
          <NavLink key={path} to={path} className={`tab ${on ? "on" : ""}`}>
            <Icon size={22} />
            {label}
          </NavLink>
        );
      })}
    </nav>
  );
}
