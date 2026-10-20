import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import Help from "../components/Help";
import PeriodPicker, { currentPeriod, periodLabel } from "../components/PeriodPicker";
import { CHART, ErrorNotice, Progress, Stat } from "../components/ui";
import { money, pct } from "../format";
import { useApi } from "../hooks";
import type { Dashboard as DashboardData } from "../types-finance";

const crc = (v: string | number) => money(v, "CRC");
const compact = (v: number) => new Intl.NumberFormat("es-CR", { notation: "compact" }).format(v);
const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const monthTick = (m: string) => `${MONTHS[Number(m.slice(5, 7)) - 1]} ${m.slice(2, 4)}`;
const tooltipStyle = {
  contentStyle: { background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 10, fontSize: 13 },
  labelStyle: { color: "var(--muted)" },
};

function CardTitle({ title, topic, aside }: { title: string; topic: string; aside?: React.ReactNode }) {
  return (
    <div className="card-head">
      <div className="title-row">
        <h2>{title}</h2>
        <Help topic={topic} />
      </div>
      {aside}
    </div>
  );
}

export default function Dashboard() {
  const [period, setPeriod] = useState(currentPeriod("month"));
  const [more, setMore] = useState(false);
  const { data, error } = useApi<DashboardData>(`/dashboard?period=${period}`);
  const isYear = period.length === 4;

  const categories = data ? Object.entries(data.by_category).map(([name, value]) => ({ name, value: Number(value) })) : [];
  const trend =
    data?.trend.map((p) => ({
      month: p.month,
      Ingresos: Number(p.income),
      Gastos: Number(p.expenses),
      Neto: Number(p.income) - Number(p.expenses),
      Ahorro: Number(p.income) ? (Number(p.income) - Number(p.expenses)) / Number(p.income) : null,
    })) ?? [];
  const daily =
    data?.daily.map((d) => ({
      label: isYear ? monthTick(d.date) : d.date.slice(8, 10),
      Gasto: Number(d.expenses),
      Acumulado: Number(d.cumulative_expenses),
    })) ?? [];
  const weekday = data ? Object.entries(data.by_weekday).map(([d, v]) => ({ d, v: Number(v) })) : [];
  const currencies = data
    ? Object.entries(data.expenses_by_currency).map(([c, v]) => ({ name: c, value: c === "USD" ? Number(v) * Number(data.fx?.sell ?? 0) : Number(v) }))
    : [];
  const income = Number(data?.income ?? 0);
  const net = Number(data?.net ?? 0);
  const top = categories[0];
  const expenses = Number(data?.expenses ?? 0);
  // El hallazgo del periodo: lo primero que se lee bajo el título.
  const finding = !data
    ? ""
    : expenses === 0 && income === 0
      ? "Todavía no hay movimientos en este periodo."
      : (net < 0
          ? `Salieron ${crc(-net)} más de lo que entró.`
          : `Te quedaron ${crc(net)} (${pct(net / (income || 1), 0)} de lo que entró).`) +
        (top ? ` Lo que más pesa: ${top.name.toLowerCase()}, ${pct(top.value / (expenses || 1), 0)} del gasto.` : "");

  return (
    <>
      <div className="page-head">
        <div>
          <div className="title-row">
            <h1>{isYear ? `Tu año ${period}` : `Resumen de ${periodLabel(period).toLowerCase()}`}</h1>
            <Help topic="resumen" />
          </div>
          <div className="muted">{finding || "Cargando…"}</div>
        </div>
        <PeriodPicker value={period} onChange={setPeriod} allowYear />
      </div>
      <ErrorNotice error={error} />

      {data && (
        <>
          {(data.pending_categorization > 0 || data.unread_alerts > 0) && (
            <div className="notice warn">
              {data.pending_categorization > 0 && (
                <Link to="/transacciones?status=suggested">{data.pending_categorization} transacciones por confirmar</Link>
              )}
              {data.pending_categorization > 0 && data.unread_alerts > 0 && " · "}
              {data.unread_alerts > 0 && <Link to="/alertas">{data.unread_alerts} alertas sin leer</Link>}
            </div>
          )}

          <div className="grid grid-4">
            <Stat
              lead
              label="Neto"
              value={<span className={net < 0 ? "neg" : "pos"}>{crc(data.net)}</span>}
              hint={income ? `Tasa de ahorro ${pct(net / income, 0)}` : "Sin ingresos registrados"}
            />
            <Stat label="Ingresos" value={crc(data.income)} />
            <Stat
              label="Gastos"
              value={crc(data.expenses)}
              hint={
                Object.keys(data.expenses_by_currency).some((c) => c !== "CRC")
                  ? Object.entries(data.expenses_by_currency)
                      .map(([c, v]) => money(v, c))
                      .join(" + ")
                  : "Todo en colones"
              }
            />
            <Stat
              label="Dólar hoy"
              value={data.fx ? `₡${Number(data.fx.sell).toFixed(2)}` : "—"}
              hint={
                data.fx
                  ? data.fx.source === "BCCR"
                    ? `BCCR · compra ₡${Number(data.fx.buy).toFixed(2)} · ${data.fx.rate_date}`
                    : `Mercado (Yahoo) · ${data.fx.rate_date}`
                  : "Sin datos"
              }
            />
          </div>

          <div className="grid grid-2">
            <div className="card">
              <CardTitle title="Gasto por categoría" topic="resumen.categorias" />
              {categories.length === 0 ? (
                <p className="muted">Sin gastos en este periodo.</p>
              ) : (
                <ol className="rank">
                  {categories.slice(0, 7).map((c, i) => (
                    <li key={c.name} className={c.name === "Sin categoría" ? "unset" : i === 0 ? "top" : ""}>
                      <span className="rank-name">{c.name}</span>
                      <span className="rank-val">{crc(c.value)}</span>
                      <span className="rank-share">{pct(c.value / (expenses || 1), 0)}</span>
                      <span className="rank-bar" aria-hidden>
                        <span style={{ width: `${(c.value / (categories[0]?.value || 1)) * 100}%` }} />
                      </span>
                    </li>
                  ))}
                </ol>
              )}
              {categories.length > 7 && <p className="muted small">Y {categories.length - 7} categorías más.</p>}
              <div className="card-foot">
                <Link to="/transacciones">{data.pending_categorization ? `Categorizar ${data.pending_categorization} pendientes` : "Ver transacciones"}</Link>
              </div>
            </div>
            <div className="card">
              <CardTitle title={isYear ? `Mes a mes, ${period}` : "Últimos 12 meses"} topic="resumen.evolucion" />
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={trend}>
                  <CartesianGrid vertical={false} stroke={CHART.grid} />
                  <XAxis dataKey="month" tickFormatter={monthTick} tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={compact} tick={{ fontSize: 11 }} width={48} />
                  <Tooltip formatter={(v) => crc(Number(v))} labelFormatter={(l) => monthTick(String(l))} {...tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar isAnimationActive={false} dataKey="Ingresos" fill={CHART.accent} radius={[4, 4, 0, 0]} />
                  <Bar isAnimationActive={false} dataKey="Gastos" fill={CHART.danger} radius={[4, 4, 0, 0]} />
                  <Line isAnimationActive={false} dataKey="Neto" stroke={CHART.warn} strokeWidth={2} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card">
            <CardTitle title={isYear ? "Ritmo de gasto del año" : "Ritmo de gasto del mes"} topic="resumen.ritmo" />
            <ResponsiveContainer width="100%" height={240}>
              <ComposedChart data={daily}>
                <defs>
                  <linearGradient id="cumul" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor={CHART.danger} stopOpacity={0.25} />
                    <stop offset="100%" stopColor={CHART.danger} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke={CHART.grid} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={isYear ? 0 : 2} />
                <YAxis yAxisId="d" tickFormatter={compact} tick={{ fontSize: 11 }} width={48} />
                <YAxis yAxisId="c" orientation="right" tickFormatter={compact} tick={{ fontSize: 11 }} width={52} />
                <Tooltip formatter={(v) => crc(Number(v))} {...tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar isAnimationActive={false} yAxisId="d" dataKey="Gasto" name={isYear ? "Gasto del mes" : "Gasto del día"} fill={CHART.accent2} radius={[3, 3, 0, 0]} />
                <Area isAnimationActive={false} yAxisId="c" dataKey="Acumulado" stroke={CHART.danger} fill="url(#cumul)" strokeWidth={2} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="more-toggle">
            <button onClick={() => setMore(!more)} aria-expanded={more}>
              {more ? "Ocultar análisis adicional ▲" : "Mostrar más análisis ▼"}
            </button>
          </div>

          {more && (
            <>
              <div className="grid grid-2">
                <div className="card">
                  <CardTitle title="Dónde más gastás" topic="resumen.mas" />
                  <table>
                    <tbody>
                      {data.top_merchants.map((m, i) => (
                        <tr key={m.merchant}>
                          <td className="muted mono" style={{ width: 28 }}>
                            {i + 1}
                          </td>
                          <td>
                            {m.merchant}
                            <div className="small muted">
                              {m.count} {m.count === 1 ? "movimiento" : "movimientos"}
                            </div>
                          </td>
                          <td className="num">{crc(m.amount)}</td>
                          <td style={{ width: "30%" }}>
                            <Progress ratio={Number(m.amount) / Number(data.top_merchants[0]?.amount || 1)} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="card">
                  <CardTitle title="Gasto por día de la semana" topic="resumen.mas" />
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={weekday}>
                      <CartesianGrid vertical={false} stroke={CHART.grid} />
                      <XAxis dataKey="d" tick={{ fontSize: 12 }} />
                      <YAxis tickFormatter={compact} tick={{ fontSize: 11 }} width={48} />
                      <Tooltip formatter={(v) => crc(Number(v))} {...tooltipStyle} cursor={{ fill: "var(--surface-2)" }} />
                      <Bar isAnimationActive={false} dataKey="v" name="Gasto" fill={CHART.warn} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div className="grid grid-2">
                <div className="card">
                  <CardTitle title="Tasa de ahorro por mes" topic="resumen" />
                  <ResponsiveContainer width="100%" height={220}>
                    <ComposedChart data={trend}>
                      <CartesianGrid vertical={false} stroke={CHART.grid} />
                      <XAxis dataKey="month" tickFormatter={monthTick} tick={{ fontSize: 11 }} />
                      <YAxis tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tick={{ fontSize: 11 }} width={48} />
                      <Tooltip formatter={(v) => pct(Number(v), 0)} labelFormatter={(l) => monthTick(String(l))} {...tooltipStyle} />
                      <Line isAnimationActive={false} dataKey="Ahorro" stroke={CHART.accent} strokeWidth={2} connectNulls />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                <div className="card">
                  <CardTitle title="Gasto por moneda" topic="resumen" />
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie isAnimationActive={false} data={currencies} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3}>
                        {currencies.map((c, i) => (
                          <Cell key={c.name} fill={CHART.palette[i]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v) => crc(Number(v))} {...tooltipStyle} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </>
          )}

          <div className="grid grid-2">
            <div className="card">
              <CardTitle title={isYear ? "Presupuestos del año" : "Presupuestos"} topic="presupuesto" />
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
                    <span className="muted mono">
                      {money(b.spent, b.currency)} / {money(b.budgeted, b.currency)}
                    </span>
                  </div>
                  <Progress ratio={b.ratio} />
                </div>
              ))}
            </div>
            <div className="card">
              <CardTitle title="Metas de ahorro" topic="metas" />
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
                    <span className="muted mono">
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
