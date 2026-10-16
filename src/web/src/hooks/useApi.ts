import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiGet, apiPost, type ActionResult } from "../api";
import { useToast } from "../components/ui";
import { getWebApp } from "../telegram";

export type LoadStatus = "loading" | "ready" | "not-registered" | "no-telegram" | "error";

/**
 * Данные экрана: GET `path` при монтировании и по `reload()`. Различает «нет Telegram»
 * (открыто в обычном браузере), 404 «игрок не жал /start» и прочие ошибки. Устаревшие ответы
 * (сменился `path` до прихода ответа) отбрасываются.
 */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<LoadStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    if (path === null) return;
    if (!getWebApp()?.initData) {
      setStatus("no-telegram");
      return;
    }
    const id = ++requestId.current;
    try {
      const result = await apiGet<T>(path);
      if (id !== requestId.current) return;
      setData(result);
      setStatus("ready");
    } catch (err) {
      if (id !== requestId.current) return;
      if (err instanceof ApiError && err.status === 404) {
        setStatus("not-registered");
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  }, [path]);

  useEffect(() => {
    setStatus((s) => (s === "ready" ? s : "loading"));
    void load();
  }, [load]);

  return { data, status, error, reload: load };
}

/**
 * Действие (POST) с тостом результата и перезагрузкой экрана. `busy` — блокирует повторное
 * нажатие, пока запрос в пути (сервер всё равно защищён локами — это UX-предохранитель).
 */
export function useAction(onDone?: () => void | Promise<void>) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const run = useCallback(
    async (path: string, body: unknown = {}) => {
      if (busy) return null;
      setBusy(true);
      try {
        const result = await apiPost<ActionResult & Record<string, unknown>>(path, body);
        if (result.message) toast(result.message, "ok");
        getWebApp()?.HapticFeedback?.notificationOccurred?.("success");
        await onDone?.();
        return result;
      } catch (err) {
        toast(err instanceof Error ? err.message : String(err), "err");
        getWebApp()?.HapticFeedback?.notificationOccurred?.("error");
        return null;
      } finally {
        setBusy(false);
      }
    },
    [busy, onDone, toast],
  );

  return { run, busy };
}
