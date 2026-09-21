import { useEffect, useState } from "react";
import { ApiError, fetchProfile, type Profile } from "../api";
import { getWebApp } from "../telegram";

export type ProfileStatus = "loading" | "ready" | "not-registered" | "no-telegram" | "error";

// Профиль — единственная вкладка с реальным backend'ом (GET /api/profile, см. CLAUDE.md).
// Различает 4 конечных состояния явно, а не одним общим "error": нет Telegram.WebApp
// вообще (тестирование в обычном браузере — initData пустая, запрос даже не имеет смысла
// слать), 404 (игрок ни разу не жал /start боту — строки в users нет) и прочие ошибки сети/
// сервера.
export function useProfile() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [status, setStatus] = useState<ProfileStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!getWebApp()) {
      setStatus("no-telegram");
      return;
    }

    fetchProfile()
      .then((data) => {
        setProfile(data);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) {
          setStatus("not-registered");
          return;
        }
        setErrorMessage(err instanceof Error ? err.message : String(err));
        setStatus("error");
      });
  }, []);

  return { profile, status, errorMessage };
}
