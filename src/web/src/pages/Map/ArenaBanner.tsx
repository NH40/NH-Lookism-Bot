import { Swords } from "lucide-react";
import { Link } from "react-router-dom";
import { Panel } from "../../components/ui";
import { battlePath } from "../../constants/constants";
import { useApi } from "../../hooks/useApi";

/** Идёт онлайн-бой — вернуться в него (пока тебя нет, ходит автоатака). */
export function ArenaBanner() {
  const { data } = useApi<{ id: string | null }>("/arena/current");
  if (!data?.id) return null;
  return (
    <Panel title="Идёт бой" tone="red">
      <Link className="btn red block" to={battlePath(data.id)}><Swords size={16} /> Вернуться в бой</Link>
    </Panel>
  );
}
