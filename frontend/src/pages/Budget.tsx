import { useState } from "react";

import { api, type Category } from "../api";
import { ErrorNotice, Progress } from "../components/ui";
import { currentMonth, money, pct } from "../format";
import { useApi } from "../hooks";
import type { BudgetStatus } from "../types-finance";

export default function Budget() {
  const [month, setMonth] = useState(currentMonth());
  const budgets = useApi<BudgetStatus[]>(`/budgets?month=${month}`);
  const cats = useApi<Category[]>("/categories");
  const [form, setForm] = useState({ category_id: 0, amount: "", currency: "CRC", onlyThisMonth: false });
  const [error, setError] = useState<string>();

  async function save() {
    setError(undefined);
    try {
      await api.post("/budgets", {
        category_id: form.category_id,
        amount: form.amount,
        currency: form.currency,
        month: form.onlyThisMonth ? `${month}-01` : null,
      });
      setForm({ ...form, amount: "" });
      budgets.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove(id: number) {
    await api.del(`/budgets/${id}`);
    budgets.reload();
  }

  const expenseCats = cats.data?.filter((c) => c.kind === "expense") ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Presupuesto mensual</h1>
          <div className="muted">
            Un presupuesto puede estar en colones o dólares; el gasto en la otra moneda se convierte con el BCCR.
          </div>
        </div>
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
      </div>
      <ErrorNotice error={error ?? budgets.error} />

      <div className="card">
        <h2>Agregar o actualizar</h2>
        <div className="row end">
          <label className="field">
            Categoría
            <select value={form.category_id} onChange={(e) => setForm({ ...form, category_id: Number(e.target.value) })}>
              <option value={0} disabled>
                Elegir…
              </option>
              {expenseCats.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Monto
            <input type="number" min="0" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </label>
          <label className="field">
            Moneda
            <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
              <option>CRC</option>
              <option>USD</option>
            </select>
          </label>
          <label className="row small">
            <input
              type="checkbox"
              checked={form.onlyThisMonth}
              onChange={(e) => setForm({ ...form, onlyThisMonth: e.target.checked })}
            />
            Solo para {month}
          </label>
          <button className="primary" disabled={!form.category_id || !form.amount} onClick={save}>
            Guardar
          </button>
        </div>
      </div>

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Categoría</th>
              <th className="num">Presupuesto</th>
              <th className="num">Gastado</th>
              <th className="num">Disponible</th>
              <th style={{ width: "25%" }}>Avance</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {budgets.data?.map((b) => (
              <tr key={b.budget_id}>
                <td>
                  {b.category} {b.is_override && <span className="badge">solo este mes</span>}
                </td>
                <td className="num">{money(b.budgeted, b.currency)}</td>
                <td className="num">{money(b.spent, b.currency)}</td>
                <td className={`num ${Number(b.remaining) < 0 ? "neg" : ""}`}>{money(b.remaining, b.currency)}</td>
                <td>
                  <div className="row">
                    <div style={{ flex: 1 }}>
                      <Progress ratio={b.ratio} />
                    </div>
                    <span className="small muted">{pct(b.ratio, 0)}</span>
                  </div>
                </td>
                <td>
                  <button className="link small" onClick={() => remove(b.budget_id)}>
                    Quitar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
