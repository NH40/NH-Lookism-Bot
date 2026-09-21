import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import { NavTabs } from "./components/NavTabs";
import {
  ROUTE_CLANS,
  ROUTE_DEVELOPMENT,
  ROUTE_MAP,
  ROUTE_PROFILE,
  ROUTE_QUESTS,
  ROUTE_SETTINGS,
  ROUTE_SHOP,
} from "./constants";
import { ClansPage } from "./pages/ClansPage";
import { DevelopmentPage } from "./pages/DevelopmentPage";
import { MapPage } from "./pages/MapPage";
import { ProfilePage } from "./pages/ProfilePage";
import { QuestsPage } from "./pages/QuestsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ShopPage } from "./pages/ShopPage";
import { applyTelegramTheme, getWebApp } from "./telegram";

export function App() {
  // Тема + ready()/expand() — один раз при старте (см. CLAUDE.md UAP, тот же приём).
  // Безопасный no-op вне Telegram (applyTelegramTheme проверяет наличие WebApp сама,
  // getWebApp() здесь просто возвращает null и optional chaining ничего не вызывает).
  useEffect(() => {
    applyTelegramTheme();
    const webApp = getWebApp();
    webApp?.ready();
    webApp?.expand();
  }, []);

  return (
    <div className="screen">
      <NavTabs />
      <main className="page-body">
        <Routes>
          <Route path={ROUTE_PROFILE} element={<ProfilePage />} />
          <Route path={ROUTE_MAP} element={<MapPage />} />
          <Route path={ROUTE_DEVELOPMENT} element={<DevelopmentPage />} />
          <Route path={ROUTE_SHOP} element={<ShopPage />} />
          <Route path={ROUTE_CLANS} element={<ClansPage />} />
          <Route path={ROUTE_QUESTS} element={<QuestsPage />} />
          <Route path={ROUTE_SETTINGS} element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
