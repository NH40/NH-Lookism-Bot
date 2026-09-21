// Пути маршрутов react-router-dom — сравниваются в NavTabs (подсветка активной вкладки) и
// используются в <Route>/<NavLink>, тот же принцип, что CB_ в боте (см. CLAUDE.md UAP,
// "config/ vs constants/"): значение задаётся один раз здесь, не дублируется строковым
// литералом в App.tsx/NavTabs.tsx.
export const ROUTE_PROFILE = "/";
export const ROUTE_MAP = "/map";
export const ROUTE_DEVELOPMENT = "/development";
export const ROUTE_SHOP = "/shop";
export const ROUTE_CLANS = "/clans";
export const ROUTE_QUESTS = "/quests";
export const ROUTE_SETTINGS = "/settings";
