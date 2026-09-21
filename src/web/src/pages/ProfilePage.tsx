import { AlertTriangle, Flag, Loader2, MapPin, ShieldAlert, User } from "lucide-react";
import { PHASE_LABELS } from "../config";
import { useProfile } from "../hooks/useProfile";

// Единственная реально работающая вкладка — GET /api/profile (см. CLAUDE.md, раздел про
// новый эндпоинт). Остальные 6 вкладок — PlaceholderPage.
export function ProfilePage() {
  const { profile, status, errorMessage } = useProfile();

  if (status === "loading") {
    return (
      <div className="screen center">
        <Loader2 size={22} className="spin" /> Загрузка…
      </div>
    );
  }

  if (status === "no-telegram") {
    return (
      <div className="screen center error">
        <ShieldAlert size={20} />
        Открой это приложение через Telegram, чтобы увидеть профиль.
      </div>
    );
  }

  if (status === "not-registered") {
    return (
      <div className="screen center error">
        <AlertTriangle size={20} />
        Открой бота и нажми /start, чтобы зарегистрироваться.
      </div>
    );
  }

  if (status === "error" || !profile) {
    return (
      <div className="screen center error">
        <AlertTriangle size={20} />
        {errorMessage ?? "Не удалось загрузить профиль."}
      </div>
    );
  }

  return (
    <div className="profile-page">
      <div className="app-header">
        <div className="app-header-name">
          <User size={18} /> {profile.display_name ?? "Игрок"}
        </div>
        {profile.username && <div className="profile-username">@{profile.username}</div>}
      </div>

      <div className="profile-card">
        <div className="profile-row">
          <span className="profile-row-label">
            <Flag size={16} /> Банда
          </span>
          <span>{profile.gang_name ?? "—"}</span>
        </div>
        <div className="profile-row">
          <span className="profile-row-label">
            <MapPin size={16} /> Страна
          </span>
          <span>{profile.country?.name ?? "—"}</span>
        </div>
        <div className="profile-row">
          <span className="profile-row-label">
            <MapPin size={16} /> Город
          </span>
          <span>
            {profile.city ? `${profile.city.name} (районов: ${profile.city.district_count})` : "—"}
          </span>
        </div>
        <div className="profile-row">
          <span className="profile-row-label">Фаза</span>
          <span>{PHASE_LABELS[profile.phase] ?? profile.phase}</span>
        </div>
      </div>

      <div className="placeholder-body profile-footer-note">
        Остальные разделы профиля (характеристики, мастерство, уникальные системы, клан)
        появятся по мере реализации соответствующих доменов.
      </div>
    </div>
  );
}
