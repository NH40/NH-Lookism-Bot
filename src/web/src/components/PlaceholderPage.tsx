import type { ComponentType } from "react";

interface PlaceholderPageProps {
  icon: ComponentType<{ size?: number }>;
  title: string;
}

// Честная заглушка для 6 вкладок без backend'а (см. CLAUDE.md — только `country`/`city`/
// `profile` реализованы по-настоящему, остальные 25 api/routers/*.py — пустые TODO-роутеры).
// Никаких выдуманных цифр/механик — только нейтральная строка "в разработке".
export function PlaceholderPage({ icon: Icon, title }: PlaceholderPageProps) {
  return (
    <div className="screen center placeholder">
      <Icon size={32} />
      <div className="placeholder-title">{title}</div>
      <div className="placeholder-body">Раздел в разработке.</div>
    </div>
  );
}
