import { Swords } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { apiGet } from "../api";
import { battlePath } from "../constants/constants";
import { getWebApp } from "../telegram";

// Идёт онлайн-бой (2026-11-20): плашка «Войти в бой» поверх любого экрана — соперник принял вызов,
// а игрок где-то в профиле; пока его нет, за него ходит автоатака.
export function LiveBattleDock() {
  const [id, setId] = useState<string | null>(null);
  const { pathname } = useLocation();
  const nav = useNavigate();
  const inBattle = pathname.startsWith("/battle/");
  useEffect(() => {
    if (!getWebApp()?.initData) return;
    let alive = true;
    const load = () => apiGet<{ id: string | null }>("/arena/current").then((d) => alive && setId(d.id)).catch(() => undefined);
    load();
    const t = setInterval(load, 8000);
    return () => { alive = false; clearInterval(t); };
  }, [pathname]);
  if (!id || inBattle) return null;
  return (
    <button type="button" className="battle-dock" onClick={() => nav(battlePath(id))}>
      <Swords size={18} />
      <span><b>Идёт бой!</b><small>Нажми, чтобы войти — иначе ходит автоатака</small></span>
    </button>
  );
}
