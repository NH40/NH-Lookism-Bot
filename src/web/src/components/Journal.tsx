import { ScrollText } from "lucide-react";

// Ход боя: шпионы перед боем, раунды, сработавшие навыки позиций, итог — свёрнуто по умолчанию.
export function Journal({ lines }: { lines?: string[] }) {
  if (!lines || lines.length === 0) return null;
  return (
    <details className="journal">
      <summary><ScrollText size={14} />Ход боя</summary>
      <div className="journal-body">
        {lines.map((line, i) => (
          <div key={i} className={line.startsWith("Раунд") ? "jr" : line.startsWith("Итог") ? "jt" : ""}>{line}</div>
        ))}
      </div>
    </details>
  );
}
