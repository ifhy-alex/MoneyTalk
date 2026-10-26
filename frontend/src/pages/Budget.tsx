import { useState } from "react";

import { api, type Category } from "../api";
import BudgetHarp from "../art/BudgetHarp";
import TensionWave from "../art/TensionWave";
import { ErrorNotice } from "../components/ui";
import { currentMonth, money, pct } from "../format";
import { useApi } from "../hooks";
import type { BudgetStatus, Dashboard } from "../types-finance";
import Help from "../components/Help";
import PeriodPicker from "../components/PeriodPicker";

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
  // Avance del calendario en el mes seleccionado (0…1) para comparar ritmo de gasto vs día del mes.
  const calendarRatio = (() => {
    const now = new Date();
    const cur = currentMonth();
    if (month < cur) return 1;
    if (month > cur) return 0;
    const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
    return Math.min(1, now.getDate() / daysInMonth);
  })();
  // Referencia para empezar: tu gasto mensual promedio por categoría en lo que va del año.
  const year = useApi<Dashboard>(budgets.data && budgets.data.length === 0 ? `/dashboard?period=${month.slice(0, 4)}` : null);
  const monthsWithData = Math.max(1, year.data?.trend.filter((t) => Number(t.expenses) > 0).length ?? 1);
  const suggestions = Object.entries(year.data?.by_category ?? {})
    .map(([name, total]) => ({ cat: expenseCats.find((c) => c.name === name), avg: Math.round(Number(total) / monthsWithData / 1000) * 1000 }))
    .filter((s): s is { cat: Category; avg: number } => Boolean(s.cat) && s.avg > 0)
    .slice(0, 6);

  async function applySuggestion(categoryId: number, amount: number) {
    setError(undefined);
    try {
      await api.post("/budgets", { category_id: categoryId, amount: String(amount), currency: "CRC", month: null });
      budgets.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <div className="title-row">
            <h1>Presupuesto mensual</h1>
            <Help topic="presupuesto" />
          </div>
          <div className="muted">
            Un presupuesto puede estar en colones o dólares; el gasto en la otra moneda se convierte con el BCCR.
          </div>
        </div>
        <PeriodPicker value={month} onChange={setMonth} />
      </div>
      <ErrorNotice error={error ?? budgets.error} />

      {budgets.data && budgets.data.length > 0 && (
        <figure className="card art-band">
          <BudgetHarp
            strings={budgets.data.map((b) => ({ category: b.category, ratio: b.ratio }))}
            calendarRatio={calendarRatio}
            label={`Diapasón de ${budgets.data.length} presupuestos frente al avance del mes`}
          />
          <figcaption>
            Todas tus categorías presupuestadas como cuerdas de un diapasón: la aguja dorada marca el día del mes en el que
            vas ({Math.round(calendarRatio * 100)} %). Las cuerdas que vibran más allá de la aguja van adelantadas al
            calendario.
          </figcaption>
        </figure>
      )}

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
                      <TensionWave ratio={b.ratio} label={`${b.category}: ${pct(b.ratio, 0)} del presupuesto`} />
                    </div>
                    <span className={`small ${b.ratio >= 1 ? "neg" : "muted"}`}>{pct(b.ratio, 0)}</span>
                  </div>
                </td>
                <td>
                  <button className="link small" onClick={() => remove(b.budget_id)}>
                    Quitar
                  </button>
                </td>
              </tr>
            ))}
            {budgets.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="empty-row">
                  Todavía no tenés presupuestos para {month}. Empezá con tu gasto real: abajo está tu promedio mensual por
                  categoría.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {budgets.data?.length === 0 && (
        <div className="card table-wrap">
          <div className="card-head">
            <h2>Tu gasto promedio por categoría</h2>
            <span className="muted small">
              {month.slice(0, 4)} · {monthsWithData} {monthsWithData === 1 ? "mes" : "meses"} con datos
            </span>
          </div>
          {suggestions.length === 0 ? (
            <p className="muted">Todavía no hay gastos categorizados. Confirmá categorías en Transacciones y aquí aparecerán.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Categoría</th>
                  <th className="num">Promedio mensual</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {suggestions.map((s) => (
                  <tr key={s.cat.id}>
                    <td>{s.cat.name}</td>
                    <td className="num">{money(s.avg, "CRC")}</td>
                    <td className="num">
                      <button onClick={() => applySuggestion(s.cat.id, s.avg)}>Usar como presupuesto</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </>
  );
}
