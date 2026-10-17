import { useEffect } from "react";
import { Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { NavTabs } from "./components/NavTabs";
import { ToastProvider } from "./components/ui";
import {
  ROUTE_ADMIN,
  ROUTE_ADMIN_PLAYER,
  ROUTE_ADMIN_SECTION,
  ROUTE_BUSINESS,
  ROUTE_CARDS,
  ROUTE_EMPIRE,
  ROUTE_COUNTRY,
  ROUTE_STATS,
  ROUTE_INTEL,
  ROUTE_GUIDE,
  ROUTE_CASINO,
  ROUTE_CLAN,
  ROUTE_DEVELOPMENT,
  ROUTE_DONATE,
  ROUTE_EXCHANGE,
  ROUTE_GANG,
  ROUTE_MAP,
  ROUTE_MAP_EVENTS,
  ROUTE_MARKET,
  ROUTE_MORE,
  ROUTE_PROFILE,
  ROUTE_QUESTS,
  ROUTE_SETTINGS,
  ROUTE_SHOP,
  ROUTE_TRAINING,
  ROUTE_MASTERY,
  ROUTE_TOP,
} from "./constants";
import { AdminPage, AdminPlayerPage, AdminSectionPage } from "./pages/Admin";
import { BusinessPage } from "./pages/Business";
import { CardsPage } from "./pages/Cards";
import { CasinoPage } from "./pages/Casino";
import { ClanPage } from "./pages/Clan";
import { DevelopmentPage } from "./pages/Development";
import { DonatePage } from "./pages/Donate";
import { ExchangePage } from "./pages/Exchange";
import { GangPage } from "./pages/Gang";
import { MapPage } from "./pages/Map";
import { MapEventsPage } from "./pages/MapEvents";
import { MarketPage } from "./pages/Market";
import { MorePage } from "./pages/More";
import { ProfilePage } from "./pages/Profile";
import { QuestsPage } from "./pages/Quests";
import { SettingsPage } from "./pages/Settings";
import { ShopPage } from "./pages/Shop";
import { TrainingPage } from "./pages/Training";
import { MasteryPage } from "./pages/Mastery";
import { EmpirePage } from "./pages/Empire";
import { CountryPage } from "./pages/Country";
import { StatsPage } from "./pages/Stats";
import { IntelPage } from "./pages/Intel";
import { GuidePage } from "./pages/Guide";
import { TopPage } from "./pages/Top";
import { getWebApp } from "./telegram";

const TOP_LEVEL = new Set([ROUTE_PROFILE, ROUTE_MAP, ROUTE_DEVELOPMENT, ROUTE_QUESTS, ROUTE_MORE]);

export function App() {
  const location = useLocation();
  const navigate = useNavigate();

  // Тёмная тема приложения фиксирована (макет), шапку и фон Telegram красим в тон.
  useEffect(() => {
    const webApp = getWebApp();
    webApp?.ready();
    webApp?.expand();
    webApp?.setHeaderColor?.("#0a1130");
    webApp?.setBackgroundColor?.("#060a1c");
  }, []);

  // Нативная кнопка «Назад» Telegram — на вложенных экранах.
  useEffect(() => {
    const back = getWebApp()?.BackButton;
    if (!back) return;
    const goBack = () => navigate(-1);
    if (TOP_LEVEL.has(location.pathname)) {
      back.hide();
    } else {
      back.show();
      back.onClick(goBack);
    }
    return () => back.offClick(goBack);
  }, [location.pathname, navigate]);

  // Фигурные скобки обязательны: в свежих Chromium `scrollTo` возвращает Promise, и стрелка без
  // скобок отдала бы его React как функцию очистки — падение на первом же переходе.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  return (
    <ToastProvider>
      <div className="app">
        <Routes>
          <Route path={ROUTE_PROFILE} element={<ProfilePage />} />
          <Route path={ROUTE_ADMIN} element={<AdminPage />} />
          <Route path={ROUTE_ADMIN_SECTION} element={<AdminSectionPage />} />
          <Route path={ROUTE_ADMIN_PLAYER} element={<AdminPlayerPage />} />
          <Route path={ROUTE_MAP} element={<MapPage />} />
          <Route path={ROUTE_MAP_EVENTS} element={<MapEventsPage />} />
          <Route path={ROUTE_GANG} element={<GangPage />} />
          <Route path={ROUTE_CARDS} element={<CardsPage />} />
          <Route path={ROUTE_EMPIRE} element={<EmpirePage />} />
          <Route path={ROUTE_COUNTRY} element={<CountryPage />} />
          <Route path={ROUTE_STATS} element={<StatsPage />} />
          <Route path={ROUTE_INTEL} element={<IntelPage />} />
          <Route path={ROUTE_GUIDE} element={<GuidePage />} />
          <Route path={ROUTE_DEVELOPMENT} element={<DevelopmentPage />} />
          <Route path={ROUTE_TRAINING} element={<TrainingPage />} />
          <Route path={ROUTE_MASTERY} element={<MasteryPage />} />
          <Route path={ROUTE_TOP} element={<TopPage />} />
          <Route path={ROUTE_QUESTS} element={<QuestsPage />} />
          <Route path={ROUTE_MORE} element={<MorePage />} />
          <Route path={ROUTE_SHOP} element={<ShopPage />} />
          <Route path={ROUTE_CLAN} element={<ClanPage />} />
          <Route path={ROUTE_MARKET} element={<MarketPage />} />
          <Route path={ROUTE_DONATE} element={<DonatePage />} />
          <Route path={ROUTE_EXCHANGE} element={<ExchangePage />} />
          <Route path={ROUTE_CASINO} element={<CasinoPage />} />
          <Route path={ROUTE_BUSINESS} element={<BusinessPage />} />
          <Route path={ROUTE_SETTINGS} element={<SettingsPage />} />
          <Route path="*" element={<ProfilePage />} />
        </Routes>
        <NavTabs />
      </div>
    </ToastProvider>
  );
}
