import { useEffect, useState } from "react";

import { api } from "../api";
import { ErrorNotice } from "../components/ui";
import { useApi } from "../hooks";
import type { Alert, Preferences } from "../types-finance";
import Help from "../components/Help";

const KIND_LABEL: Record<string, string> = {
  unusual_spend: "Gasto inusual",
  budget_near_limit: "Presupuesto cerca del límite",
  budget_exceeded: "Presupuesto excedido",
  new_subscription: "Suscripción nueva",
  duplicate_subscription: "Suscripción duplicada",
};

export default function Alerts() {
  const alerts = useApi<Alert[]>("/alerts");
  const prefsRes = useApi<Preferences>("/preferences");
  const [prefs, setPrefs] = useState<Preferences>();
  const [message, setMessage] = useState<string>();
  const [error, setError] = useState<string>();

  useEffect(() => setPrefs(prefsRes.data), [prefsRes.data]);

  async function run(fn: () => Promise<string | void>) {
    setError(undefined);
    try {
      const msg = await fn();
      if (msg) setMessage(msg);
      alerts.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <div className="title-row">
            <h1>Alertas y ajustes</h1>
            <Help topic="alertas" />
          </div>
          <div className="muted">Cada alerta muestra la evidencia numérica que la disparó.</div>
        </div>
        <div className="row">
          <button
            onClick={() => run(async () => `${(await api.post<{ created: number }>("/alerts/run")).created} alertas nuevas`)}
          >
            Evaluar ahora
          </button>
          <button
            onClick={() =>
              run(async () => {
                await api.post("/fx/sync");
                return "Tipo de cambio actualizado";
              })
            }
          >
            Actualizar tipo de cambio
          </button>
          <button
            onClick={() =>
              run(async () => {
                await api.post("/summary/weekly");
                return "Resumen semanal enviado (si Telegram está configurado)";
              })
            }
          >
            Enviar resumen semanal
          </button>
        </div>
      </div>
      {message && <div className="notice info">{message}</div>}
      <ErrorNotice error={error} />

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tipo</th>
              <th>Mensaje</th>
              <th>Evidencia</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {alerts.data?.map((a) => (
              <tr key={a.id} style={{ opacity: a.read_at ? 0.55 : 1 }}>
                <td>
                  <span className="badge warn">{KIND_LABEL[a.kind] ?? a.kind}</span>
                </td>
                <td>{a.message}</td>
                <td className="small muted">
                  {Object.entries(a.evidence)
                    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
                    .join(" · ")}
                </td>
                <td>
                  {!a.read_at && (
                    <button className="link small" onClick={() => run(() => api.post(`/alerts/${a.id}/read`))}>
                      Marcar leída
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {alerts.data?.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  Sin alertas.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {prefs && (
        <div className="card">
          <h2>Ajustes</h2>
          <div className="row end">
            <label className="field">
              Umbral de presupuesto (%)
              <input
                type="number"
                value={Math.round(prefs.budget_alert_threshold * 100)}
                onChange={(e) => setPrefs({ ...prefs, budget_alert_threshold: Number(e.target.value) / 100 })}
              />
            </label>
            <label className="field">
              Meses del fondo de emergencia
              <input
                type="number"
                value={prefs.emergency_fund_months}
                onChange={(e) => setPrefs({ ...prefs, emergency_fund_months: Number(e.target.value) })}
              />
            </label>
            <label className="field">
              Sensibilidad gasto inusual (z)
              <input
                type="number"
                step="0.5"
                value={prefs.unusual_spend_zscore}
                onChange={(e) => setPrefs({ ...prefs, unusual_spend_zscore: Number(e.target.value) })}
              />
            </label>
            <label className="field">
              Ingreso mensual neto (vacío = estimado)
              <input
                type="number"
                value={prefs.monthly_income ?? ""}
                onChange={(e) => setPrefs({ ...prefs, monthly_income: e.target.value ? Number(e.target.value) : null })}
              />
            </label>
            <label className="field">
              Colchón que nunca se invierte (₡)
              <input
                type="number"
                value={prefs.investment_safety_buffer}
                onChange={(e) => setPrefs({ ...prefs, investment_safety_buffer: Number(e.target.value) })}
              />
            </label>
            <label className="row small">
              <input
                type="checkbox"
                checked={prefs.telegram_alerts}
                onChange={(e) => setPrefs({ ...prefs, telegram_alerts: e.target.checked })}
              />
              Enviar alertas por Telegram
            </label>
            <button
              className="primary"
              onClick={() =>
                run(async () => {
                  await api.put("/preferences", prefs);
                  return "Ajustes guardados";
                })
              }
            >
              Guardar
            </button>
          </div>
        </div>
      )}
    </>
  );
}
