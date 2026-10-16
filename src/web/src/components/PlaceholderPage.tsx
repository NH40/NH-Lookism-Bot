import { Hammer } from "lucide-react";
import { BackHeader, Panel } from "./ui";

/** Экран, который ещё не перенесён в Mini App: честная заглушка с возвратом назад. */
export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="page">
      <BackHeader title={title} />
      <Panel title={title}>
        <div className="state" style={{ minHeight: 180 }}>
          <Hammer size={26} />
          Экран переносится в Mini App — пока этот раздел доступен в боте.
        </div>
      </Panel>
    </div>
  );
}
