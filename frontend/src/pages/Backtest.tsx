import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api";
import { CHART, Disclaimer, ErrorNotice } from "../components/ui";
import { num, pct } from "../format";
import Help from "../components/Help";

interface Period {
  start: string;
  end: string;
  holdings: string[];
  evidence: Record<string, Record<string, number | null>>;
  strategy_return: number | null;
  universe_return: number | null;
  benchmark_return: number | null;
}
interface Stats {
  total: number | null;
  cagr: number | null;
  volatility: number | null;
  max_drawdown: number | null;
}
interface Result {
  periods: Period[];
  curve: { date: string; strategy: number; universe: number; benchmark: number }[];
  stats: Record<"strategy" | "universe" | "benchmark", Stats>;
  warnings: string[];
  unsupported_criteria: string[];
  skipped_symbols: Record<string, string>;
}

const METRICS: Record<string, string> = {
  pe: "P/E",
  roe: "ROE",
  debt_to_equity: "Deuda/patrimonio",
  free_cash_flow: "Flujo de caja libre",
  revenue_growth: "Crecimiento de ingresos",
  gross_margin: "Margen bruto",
  operating_margin: "Margen operativo",
  net_margin: "Margen neto",
};

interface Crit {
  metric: string;
  op: string;
  value: number;
  value_max?: number;
}

export default function Backtest() {
  const year = new Date().getFullYear();
  const [criteria, setCriteria] = useState<Crit[]>([
    { metric: "roe", op: ">=", value: 0.15 },
    { metric: "debt_to_equity", op: "<=", value: 1 },
    { metric: "pe", op: "between", value: 0, value_max: 25 },
  ]);
  const [universe, setUniverse] = useState("AAPL, MSFT, GOOGL, JNJ, PG, KO, PEP, V, MA, COST, WMT, HD, MRK, CSCO, ORCL, INTC, XOM, CVX");
  const [range, setRange] = useState({ start_year: year - 8, end_year: year - 1, rebalance_month: 4 });
  const [result, setResult] = useState<Result>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function run() {
    setBusy(true);
    setError(undefined);
    try {
      setResult(
        await api.post<Result>("/investments/backtest", {
          criteria,
          universe: universe.split(/[\s,;]+/).filter(Boolean).map((s) => s.toUpperCase()),
          ...range,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const update = (i: number, patch: Partial<Crit>) => setCriteria(criteria.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  return (
    <>
      <div className="page-head">
        <div>
          <div className="title-row">
            <h1>Backtesting</h1>
            <Help topic="backtesting" />
          </div>
          <div className="muted">
            Rebalanceo anual con estados financieros de la SEC disponibles en cada fecha (sin mirar el futuro).
          </div>
        </div>
      </div>
      <Disclaimer />
      <ErrorNotice error={error} />

      <div className="card">
        <h2>Configuración</h2>
        {criteria.map((c, i) => (
          <div className="row" key={i} style={{ marginBottom: 6 }}>
            <select value={c.metric} onChange={(e) => update(i, { metric: e.target.value })}>
              {Object.entries(METRICS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <select value={c.op} onChange={(e) => update(i, { op: e.target.value })}>
              {[">=", "<=", ">", "<", "between"].map((o) => (
                <option key={o} value={o}>
                  {o === "between" ? "entre" : o}
                </option>
              ))}
            </select>
            <input type="number" step="any" style={{ width: 100 }} value={c.value} onChange={(e) => update(i, { value: Number(e.target.value) })} />
            {c.op === "between" && (
              <input
                type="number"
                step="any"
                style={{ width: 100 }}
                value={c.value_max ?? ""}
                onChange={(e) => update(i, { value_max: Number(e.target.value) })}
              />
            )}
            <button className="link small" onClick={() => setCriteria(criteria.filter((_, j) => j !== i))}>
              Quitar
            </button>
          </div>
        ))}
        <button onClick={() => setCriteria([...criteria, { metric: "net_margin", op: ">=", value: 0.1 }])}>+ Criterio</button>
        <label className="field" style={{ marginTop: 12 }}>
          Universo
          <textarea rows={2} value={universe} onChange={(e) => setUniverse(e.target.value)} />
        </label>
        <div className="row end" style={{ marginTop: 10 }}>
          <label className="field">
            Desde
            <input type="number" value={range.start_year} onChange={(e) => setRange({ ...range, start_year: Number(e.target.value) })} />
          </label>
          <label className="field">
            Hasta
            <input type="number" value={range.end_year} onChange={(e) => setRange({ ...range, end_year: Number(e.target.value) })} />
          </label>
          <label className="field">
            Mes de rebalanceo
            <input
              type="number"
              min={1}
              max={12}
              value={range.rebalance_month}
              onChange={(e) => setRange({ ...range, rebalance_month: Number(e.target.value) })}
            />
          </label>
          <button className="primary" disabled={busy} onClick={run}>
            {busy ? "Calculando… (puede tardar la primera vez)" : "Ejecutar"}
          </button>
        </div>
      </div>

      {result && (
        <>
          <div className="notice warn">
            <b>Antes de interpretar:</b>
            <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
              {result.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>

          <div className="card table-wrap">
            <h2>Resumen</h2>
            <table>
              <thead>
                <tr>
                  <th />
                  <th className="num">Total</th>
                  <th className="num">CAGR</th>
                  <th className="num">Volatilidad anual</th>
                  <th className="num">Peor caída (entre rebalanceos)</th>
                </tr>
              </thead>
              <tbody>
                {(["strategy", "universe", "benchmark"] as const).map((k) => (
                  <tr key={k}>
                    <td>{{ strategy: "Estrategia", universe: "Universo a partes iguales", benchmark: "Índice (SPY)" }[k]}</td>
                    <td className="num">{pct(result.stats[k].total)}</td>
                    <td className="num">{pct(result.stats[k].cagr)}</td>
                    <td className="num">{pct(result.stats[k].volatility)}</td>
                    <td className="num neg">{pct(result.stats[k].max_drawdown)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={result.curve}>
                <CartesianGrid stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v: number) => num(v, 2)} />
                <Tooltip formatter={(v) => num(Number(v), 3)} />
                <Legend />
                <Line isAnimationActive={false} dataKey="strategy" name="Estrategia" stroke={CHART.accent} strokeWidth={2} />
                <Line isAnimationActive={false} dataKey="universe" name="Universo" stroke={CHART.warn} />
                <Line isAnimationActive={false} dataKey="benchmark" name="SPY" stroke={CHART.accent2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card table-wrap">
            <h2>Periodos y empresas seleccionadas</h2>
            <table>
              <thead>
                <tr>
                  <th>Periodo</th>
                  <th>Seleccionadas</th>
                  <th className="num">Estrategia</th>
                  <th className="num">Universo</th>
                  <th className="num">SPY</th>
                </tr>
              </thead>
              <tbody>
                {result.periods.map((p) => (
                  <tr key={p.start}>
                    <td className="small">
                      {p.start} → {p.end}
                    </td>
                    <td className="small">
                      {p.holdings.length ? p.holdings.join(", ") : <span className="muted">ninguna (efectivo)</span>}
                    </td>
                    <td className="num">{pct(p.strategy_return)}</td>
                    <td className="num">{pct(p.universe_return)}</td>
                    <td className="num">{pct(p.benchmark_return)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
