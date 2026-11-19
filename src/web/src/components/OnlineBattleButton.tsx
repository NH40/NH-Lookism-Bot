import { Swords } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { battlePath } from "../constants/constants";
import { useAction } from "../hooks/useApi";

/** Кнопка «Бой онлайн» (2026-11-20): старт онлайн-боя `/arena/start/...` и переход на экран боя. */
export function OnlineBattleButton({ path, body = {}, label = "Бой онлайн: перки и ходы", disabled }: {
  path: string; body?: object; label?: string; disabled?: boolean;
}) {
  const nav = useNavigate();
  const { run, busy } = useAction();
  return (
    <button type="button" className="btn gold block" style={{ marginTop: 8 }} disabled={busy || disabled}
      onClick={async () => {
        const r = (await run(path, body)) as { id?: string | null } | null;
        if (r?.id) nav(battlePath(r.id));
      }}>
      <Swords size={16} />{label}
    </button>
  );
}
