import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { CHART, ErrorNotice, Progress, Stat } from "../components/ui";
import { currentMonth, money, pct } from "../format";
import { useApi } from "../hooks";
import type { Dashboard as DashboardData } from "../types-finance";

const crc = (v: string | number) => money(v, "CRC");
const compact = (v: number) => new Intl.NumberFormat("es-CR", { notation: "compact" }).format(v);

export default function Dashboard() {
  const [month, setMonth] = useState(currentMonth());
  const { data, error } = useApi<DashboardData>(`/dashboard?month=${month}`);

  const categories = data
    ? Object.entries(data.by_category).map(([name, value]) => ({ name, value: Number(value) }))
    : [];
  const trend = data?.trend.map((p) => ({ ...p, income: Number(p.income), expenses: Number(p.expenses) })) ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Resumen</h1>
          <div className="muted">
            Montos en colones; los gastos en dólares se convierten con el tipo de venta del BCCR de cada día.
          </div>
        </div>
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
      </div>
      <ErrorNotice error={error} />

      {data && (
        <>
          {(data.pending_categorization > 0 || data.unread_alerts > 0) && (
            <div className="notice warn">
              {data.pending_categorization > 0 && (
                <Link to="/transacciones?status=suggested">
                  {data.pending_categorization} transacciones por confirmar
                </Link>
              )}
              {data.pending_categorization > 0 && data.unread_alerts > 0 && " · "}
              {data.unread_alerts > 0 && <Link to="/alertas">{data.unread_alerts} alertas sin leer</Link>}
            </div>
          )}

          <div className="grid grid-4">
            <Stat label="Ingresos" value={<span className="pos">{crc(data.income)}</span>} />
            <Stat
              label="Gastos"
              value={<span className="neg">{crc(data.expenses)}</span>}
              hint={Object.entries(data.expenses_by_currency)
                .map(([c, v]) => money(v, c))
                .join(" + ")}
            />
            <Stat label="Neto" value={crc(data.net)} hint={Number(data.income) ? `Ahorro ${pct(Number(data.net) / Number(data.income), 0)}` : undefined} />
            <Stat
              label="Tipo de cambio (venta)"
              value={data.fx ? `₡${Number(data.fx.sell).toFixed(2)}` : "—"}
              hint={data.fx ? `Compra ₡${Number(data.fx.buy).toFixed(2)} · ${data.fx.rate_date}` : "Sin datos"}
            />
          </div>

          <div className="grid grid-2">
            <div className="card">
              <h2>Gasto por categoría</h2>
              {categories.length === 0 ? (
                <p className="muted">Sin gastos este mes.</p>
              ) : (
                <ResponsiveContainer width="100%" height={Math.max(160, categories.length * 30)}>
                  <BarChart data={categories} layout="vertical" margin={{ left: 10, right: 20 }}>
                    <CartesianGrid horizontal={false} stroke={CHART.grid} />
                    <XAxis type="number" tickFormatter={compact} />
                    <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v) => crc(Number(v))} />
                    <Bar dataKey="value" name="Gasto" fill={CHART.accent} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="card">
              <h2>Últimos 6 meses</h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={trend}>
                  <CartesianGrid vertical={false} stroke={CHART.grid} />
                  <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={compact} />
                  <Tooltip formatter={(v) => crc(Number(v))} />
                  <Legend />
                  <Bar dataKey="income" name="Ingresos" fill={CHART.accent} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="expenses" name="Gastos" fill={CHART.danger} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-2">
            <div className="card">
              <h2>Presupuestos</h2>
              {data.budgets.length === 0 && (
                <p className="muted">
                  Sin presupuestos. <Link to="/presupuesto">Crear uno</Link>
                </p>
              )}
              {data.budgets.map((b) => (
                <div key={b.budget_id} style={{ marginBottom: 12 }}>
                  <div className="row small">
                    <b>{b.category}</b>
                    <span className="spacer" />
                    <span className="muted">
                      {money(b.spent, b.currency)} / {money(b.budgeted, b.currency)}
                    </span>
                  </div>
                  <Progress ratio={b.ratio} />
                </div>
              ))}
            </div>
            <div className="card">
              <h2>Metas de ahorro</h2>
              {data.goals.length === 0 && (
                <p className="muted">
                  Empezá por el <Link to="/metas">fondo de emergencia</Link>.
                </p>
              )}
              {data.goals.map((g) => (
                <div key={g.id} style={{ marginBottom: 12 }}>
                  <div className="row small">
                    <b>{g.name}</b>
                    {g.is_emergency_fund && <span className="badge ok">Prioritaria</span>}
                    <span className="spacer" />
                    <span className="muted">
                      {money(g.saved, g.currency)} / {money(g.target_amount, g.currency)}
                    </span>
                  </div>
                  <Progress ratio={g.ratio} />
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  );
}
