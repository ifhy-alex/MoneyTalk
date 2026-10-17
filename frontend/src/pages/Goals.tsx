import { useState } from "react";

import { api } from "../api";
import { ErrorNotice, Progress } from "../components/ui";
import { money, pct } from "../format";
import { useApi } from "../hooks";
import type { Goal } from "../types-finance";

interface EfSuggestion {
  months: number;
  suggested_target: string;
  currency: string;
  based_on: string;
}

const today = () => new Date().toISOString().slice(0, 10);

export default function Goals() {
  const goals = useApi<Goal[]>("/goals");
  const ef = useApi<EfSuggestion>("/goals/emergency-fund/suggestion");
  const [error, setError] = useState<string>();
  const [form, setForm] = useState({
    name: "",
    target_amount: "",
    currency: "CRC",
    target_date: "",
    monthly_contribution: "",
    is_emergency_fund: false,
  });
  const [contrib, setContrib] = useState<Record<number, string>>({});

  async function run(fn: () => Promise<unknown>) {
    setError(undefined);
    try {
      await fn();
      goals.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const hasEmergency = goals.data?.some((g) => g.is_emergency_fund);

  const createGoal = () =>
    run(async () => {
      await api.post("/goals", {
        ...form,
        target_date: form.target_date || null,
        monthly_contribution: form.monthly_contribution || null,
        priority: form.is_emergency_fund ? 1000 : 100,
      });
      setForm({ ...form, name: "", target_amount: "", monthly_contribution: "", is_emergency_fund: false });
    });

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Metas de ahorro</h1>
          <div className="muted">El fondo de emergencia siempre va primero.</div>
        </div>
      </div>
      <ErrorNotice error={error} />

      {!hasEmergency && ef.data && (
        <div className="notice warn row">
          <span>
            Sugerencia de fondo de emergencia: <b>{money(ef.data.suggested_target, ef.data.currency)}</b> (
            {ef.data.months} meses; {ef.data.based_on}).
          </span>
          <span className="spacer" />
          <button
            className="primary"
            onClick={() =>
              setForm({
                ...form,
                name: "Fondo de emergencia",
                target_amount: String(Math.round(Number(ef.data!.suggested_target))),
                currency: "CRC",
                is_emergency_fund: true,
              })
            }
          >
            Usar
          </button>
        </div>
      )}

      <div className="card">
        <h2>Nueva meta</h2>
        <div className="row end">
          <label className="field">
            Nombre
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label className="field">
            Objetivo
            <input type="number" value={form.target_amount} onChange={(e) => setForm({ ...form, target_amount: e.target.value })} />
          </label>
          <label className="field">
            Moneda
            <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
              <option>CRC</option>
              <option>USD</option>
            </select>
          </label>
          <label className="field">
            Fecha objetivo
            <input type="date" value={form.target_date} onChange={(e) => setForm({ ...form, target_date: e.target.value })} />
          </label>
          <label className="field">
            Aporte mensual
            <input
              type="number"
              value={form.monthly_contribution}
              onChange={(e) => setForm({ ...form, monthly_contribution: e.target.value })}
            />
          </label>
          <label className="row small">
            <input
              type="checkbox"
              checked={form.is_emergency_fund}
              disabled={hasEmergency}
              onChange={(e) => setForm({ ...form, is_emergency_fund: e.target.checked })}
            />
            Fondo de emergencia
          </label>
          <button className="primary" disabled={!form.name || !form.target_amount} onClick={createGoal}>
            Crear
          </button>
        </div>
      </div>

      <div className="grid grid-2">
        {goals.data?.map((g) => (
          <div className="card" key={g.id}>
            <div className="row">
              <h2 style={{ margin: 0 }}>{g.name}</h2>
              {g.is_emergency_fund && <span className="badge ok">Prioritaria</span>}
              <span className="spacer" />
              <button className="link small" onClick={() => run(() => api.del(`/goals/${g.id}`))}>
                Borrar
              </button>
            </div>
            <p className="small muted" style={{ margin: "6px 0" }}>
              {money(g.saved, g.currency)} de {money(g.target_amount, g.currency)} · {pct(g.ratio, 0)}
            </p>
            <Progress ratio={g.ratio} />
            <p className="small">
              {g.months_to_target !== null && <>Con el aporte actual llegás en {g.months_to_target} meses. </>}
              {g.required_monthly && <>Para la fecha objetivo necesitás {money(g.required_monthly, g.currency)}/mes.</>}
            </p>
            <div className="row">
              <input
                type="number"
                placeholder="Aporte (negativo = retiro)"
                value={contrib[g.id] ?? ""}
                onChange={(e) => setContrib({ ...contrib, [g.id]: e.target.value })}
              />
              <button
                disabled={!contrib[g.id]}
                onClick={() =>
                  run(async () => {
                    await api.post(`/goals/${g.id}/contributions`, { date: today(), amount: contrib[g.id] });
                    setContrib({ ...contrib, [g.id]: "" });
                  })
                }
              >
                Registrar
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
