import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "./api";

export interface Resource<T> {
  data: T | undefined;
  error: string | undefined;
  /** Código HTTP del último error, si vino de la API. */
  status: number | undefined;
  loading: boolean;
  reload: () => void;
}

interface Options {
  /** Códigos HTTP que significan "todavía no, probá de nuevo" (p. ej. 409 sin tipo de cambio). */
  retryOn?: number[];
  retryMs?: number;
}

/** Carga un recurso GET y lo recarga cuando cambia `path`. */
export function useApi<T>(path: string | null, { retryOn, retryMs = 5000 }: Options = {}): Resource<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const [status, setStatus] = useState<number>();
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    setLoading(true);
    setError(undefined);
    setStatus(undefined);
    api
      .get<T>(path)
      .then((d) => !cancelled && setData(d))
      .catch((e: Error) => {
        if (cancelled) return;
        setError(e.message);
        setStatus(e instanceof ApiError ? e.status : undefined);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [path, tick]);

  // Solo los errores transitorios se reintentan; uno real (422, 500) se muestra y ya.
  const retryKey = retryOn?.join(",");
  useEffect(() => {
    if (status === undefined || !retryKey?.split(",").includes(String(status))) return;
    const id = setTimeout(() => setTick((t) => t + 1), retryMs);
    return () => clearTimeout(id);
  }, [status, retryKey, retryMs]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, status, loading, reload };
}
