import { useState } from "react";
import { CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api";
import { CHART, Disclaimer, ErrorNotice, Stat } from "../components/ui";
import { money, num, pct } from "../format";
import Ridgeline from "../art/Ridgeline";
import { useApi } from "../hooks";
import Help from "../components/Help";

interface PositionRow {
  symbol: string;
  name: string | null;
  asset_type: string;
  currency: string;
  sector: string;
  country: string;
  quantity: string;
  avg_cost: string | null;
  cost_basis: string;
  price: string | null;
  price_source: string;
  market_value: string | null;
  unrealized_pnl: string | null;
  unrealized_pct: number | null;
  realized_pnl: string;
  weight: number | null;
}
interface PortfolioData {
  positions: PositionRow[];
  total_value_usd: string | null;
  by_sector: Record<string, number>;
  by_country: Record<string, number>;
  by_type: Record<string, number>;
  warnings: string[];
}
interface Benchmark {
  benchmark: string;
  invested_net: string;
  portfolio_value: string;
  benchmark_value: string;
  difference: string;
  series: { date: string; portfolio: string; benchmark: string; invested: string }[];
  excluded: string[];
  method: string;
}
interface Available {
  monthly_income: string;
  avg_expenses: string;
  goal_contributions: string;
  surplus: string;
  emergency_fund_gap: string;
  available_monthly: string;
  explanation: string[];
}
interface TradeRow {
  id: number;
  symbol: string;
  trade_date: string;
  side: "buy" | "sell";
  quantity: string;
  price: string;
  fees: string;
}

function AllocationPie({ title, data }: { title: string; data: Record<string, number> }) {
  const items = Object.entries(data).map(([name, value]) => ({ name, value }));
  return (
    <div className="card">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="muted small">Sin datos.</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie isAnimationActive={false} data={items} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
              {items.map((_, i) => (
                <Cell key={i} fill={CHART.palette[i % CHART.palette.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(v) => pct(Number(v))} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

const today = () => new Date().toISOString().slice(0, 10);

export default function Portfolio() {
  const port = useApi<PortfolioData>("/investments/portfolio");
  const bench = useApi<Benchmark>("/investments/portfolio/benchmark");
  const avail = useApi<Available>("/investments/available");
  const trades = useApi<TradeRow[]>("/investments/trades");
  const [form, setForm] = useState({ symbol: "", trade_date: today(), side: "buy", quantity: "", price: "", fees: "0" });
  const [error, setError] = useState<string>();

  async function addTrade() {
    setError(undefined);
    try {
      await api.post("/investments/trades", form);
      setForm({ ...form, symbol: "", quantity: "", price: "" });
      port.reload();
      bench.reload();
      trades.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function removeTrade(id: number) {
    try {
      await api.del(`/investments/trades/${id}`);
      port.reload();
      bench.reload();
      trades.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const series = bench.data?.series.map((p) => ({
    date: p.date,
    Portafolio: Number(p.portfolio),
    [bench.data!.benchmark]: Number(p.benchmark),
    Invertido: Number(p.invested),
  }));

  return (
    <>
      <div className="page-head">
        <div>
          <div className="title-row">
            <h1>Portafolio</h1>
            <Help topic="portafolio" />
          </div>
          <div className="muted">Registro manual de posiciones; precios del proveedor configurado (con caché).</div>
        </div>
      </div>
      {bench.data && bench.data.series.length > 1 && (
        <figure className="ridge-band">
          <Ridgeline
            height={130}
            sort={false}
            ridges={[
              { label: "Invertido", values: bench.data.series.map((p) => Number(p.invested)) },
              { label: bench.data.benchmark, values: bench.data.series.map((p) => Number(p.benchmark)) },
              { label: "Portafolio", values: bench.data.series.map((p) => Number(p.portfolio)) },
            ]}
            label={`Relieve de tu portafolio frente a ${bench.data.benchmark} y lo invertido`}
          />
          <figcaption>
            De atrás hacia adelante: lo que invertiste, {bench.data.benchmark} con esas mismas compras y tu portafolio.
            Cada cresta tiene su propia escala; los montos exactos están en el gráfico de abajo.
          </figcaption>
        </figure>
      )}
      <Disclaimer />
      <ErrorNotice error={error ?? port.error} />
      {port.data?.warnings.map((w) => (
        <div key={w} className="notice warn small">
          {w}
        </div>
      ))}

      {avail.data && (
        <div className="card">
          <h2>Disponible para invertir este mes</h2>
          <div className="grid grid-4">
            <Stat label="Ingreso mensual" value={money(avail.data.monthly_income, "CRC")} />
            <Stat label="Gasto promedio" value={money(avail.data.avg_expenses, "CRC")} />
            <Stat label="Aportes a metas" value={money(avail.data.goal_contributions, "CRC")} />
            <Stat label="Disponible" value={<span className="pos">{money(avail.data.available_monthly, "CRC")}</span>} />
          </div>
          <ul className="small muted">
            {avail.data.explanation.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}
      {avail.error && <div className="notice warn small">Disponible para invertir: {avail.error}</div>}

      <div className="grid grid-4">
        <Stat label="Valor total (USD)" value={port.data?.total_value_usd ? money(port.data.total_value_usd, "USD") : "—"} />
        {bench.data && (
          <>
            <Stat label="Invertido neto" value={money(bench.data.invested_net, "USD")} />
            <Stat label="Si hubiera sido el índice" value={money(bench.data.benchmark_value, "USD")} hint={bench.data.benchmark} />
            <Stat
              label="Diferencia vs. índice"
              value={<span className={Number(bench.data.difference) >= 0 ? "pos" : "neg"}>{money(bench.data.difference, "USD")}</span>}
            />
          </>
        )}
      </div>

      {series && series.length > 1 && (
        <div className="card">
          <h2>Portafolio vs. {bench.data?.benchmark}</h2>
          <p className="small muted">
            {bench.data?.method}
            {bench.data?.excluded.length ? ` Excluidos: ${bench.data.excluded.join(", ")}.` : ""}
          </p>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={series}>
              <CartesianGrid stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
              <YAxis tickFormatter={(v: number) => `$${num(v, 0)}`} width={70} />
              <Tooltip formatter={(v) => money(Number(v), "USD")} />
              <Legend />
              <Line isAnimationActive={false} dataKey="Portafolio" stroke={CHART.accent} dot={false} strokeWidth={2} />
              <Line isAnimationActive={false} dataKey={bench.data!.benchmark} stroke={CHART.accent2} dot={false} strokeWidth={2} />
              <Line isAnimationActive={false} dataKey="Invertido" stroke={CHART.grid} dot={false} strokeDasharray="4 4" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="card table-wrap">
        <h2>Posiciones</h2>
        <table>
          <thead>
            <tr>
              <th>Símbolo</th>
              <th>Sector / país</th>
              <th className="num">Cantidad</th>
              <th className="num">Costo prom.</th>
              <th className="num">Precio</th>
              <th className="num">Valor</th>
              <th className="num">Ganancia no realizada</th>
              <th className="num">Realizada</th>
              <th className="num">Peso</th>
            </tr>
          </thead>
          <tbody>
            {port.data?.positions.map((p) => (
              <tr key={p.symbol}>
                <td>
                  <b>{p.symbol}</b>
                  <div className="small muted">{p.name}</div>
                </td>
                <td className="small">
                  {p.sector}
                  <div className="muted">{p.country}</div>
                </td>
                <td className="num">{num(p.quantity, 4)}</td>
                <td className="num">{p.avg_cost ? money(p.avg_cost, p.currency) : "—"}</td>
                <td className="num" title={p.price_source}>
                  {p.price ? money(p.price, p.currency) : "—"}
                </td>
                <td className="num">{p.market_value ? money(p.market_value, p.currency) : "—"}</td>
                <td className={`num ${Number(p.unrealized_pnl) >= 0 ? "pos" : "neg"}`}>
                  {p.unrealized_pnl ? `${money(p.unrealized_pnl, p.currency)} (${pct(p.unrealized_pct)})` : "—"}
                </td>
                <td className="num">{money(p.realized_pnl, p.currency)}</td>
                <td className="num">{pct(p.weight)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-4">
        <AllocationPie title="Por sector" data={port.data?.by_sector ?? {}} />
        <AllocationPie title="Por país" data={port.data?.by_country ?? {}} />
        <AllocationPie title="Por tipo" data={port.data?.by_type ?? {}} />
      </div>

      <div className="card">
        <h2>Registrar operación</h2>
        <div className="row end">
          <label className="field">
            Símbolo
            <input value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} />
          </label>
          <label className="field">
            Fecha
            <input type="date" value={form.trade_date} onChange={(e) => setForm({ ...form, trade_date: e.target.value })} />
          </label>
          <label className="field">
            Tipo
            <select value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value })}>
              <option value="buy">Compra</option>
              <option value="sell">Venta</option>
            </select>
          </label>
          <label className="field">
            Cantidad
            <input type="number" step="any" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          </label>
          <label className="field">
            Precio
            <input type="number" step="any" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
          </label>
          <label className="field">
            Comisión
            <input type="number" step="any" value={form.fees} onChange={(e) => setForm({ ...form, fees: e.target.value })} />
          </label>
          <button className="primary" disabled={!form.symbol || !form.quantity || !form.price} onClick={addTrade}>
            Guardar
          </button>
        </div>
        <table style={{ marginTop: 12 }}>
          <tbody>
            {trades.data?.map((t) => (
              <tr key={t.id}>
                <td>{t.trade_date}</td>
                <td>{t.side === "buy" ? "Compra" : "Venta"}</td>
                <td>
                  <b>{t.symbol}</b>
                </td>
                <td className="num">{num(t.quantity, 4)}</td>
                <td className="num">{num(t.price, 4)}</td>
                <td>
                  <button className="link small" onClick={() => removeTrade(t.id)}>
                    Borrar
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
