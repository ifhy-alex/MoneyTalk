import { Fragment, useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api";
import ChartDrawer from "../components/ChartDrawer";
import Help from "../components/Help";
import { Disclaimer, ErrorNotice, Sparkline } from "../components/ui";
import { useApi } from "../hooks";
import type { Instrument, MarketOverview } from "../types-market";

type Period = "change_1d" | "change_1w" | "change_1m" | "change_3m" | "change_ytd" | "change_1y";
const PERIODS: { key: Period; label: string }[] = [
  { key: "change_1d", label: "1D" },
  { key: "change_1w", label: "1S" },
  { key: "change_1m", label: "1M" },
  { key: "change_3m", label: "3M" },
  { key: "change_ytd", label: "Año" },
  { key: "change_1y", label: "12M" },
];

const NBSP = " "; // espacio duro: el % no queda solo en otra línea

// Lo que responde "¿cómo va el mercado hoy?": índices, riesgo, el dólar en colones y refugios.
const HEADLINE = ["^GSPC", "^IXIC", "^DJI", "^VIX", "^TNX", "CRC=X", "GC=F", "BTC-USD"];

const fmtLast = (i: Instrument) =>
  i.symbol === "CRC=X"
    ? `₡${i.last.toLocaleString("es-CR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : i.symbol === "^TNX"
      ? `${i.last.toFixed(2).replace(".", ",")}${NBSP}%`
      : i.last.toLocaleString("es-CR", { maximumFractionDigits: i.last < 10 ? 4 : 2, minimumFractionDigits: 2 });

function fmtPct(v: number | null, digits = 1): string {
  if (v === null) return "—";
  const s = (v * 100).toFixed(digits).replace(".", ",");
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s.replace("-", "")}${NBSP}%`;
}

function Pct({ v, digits = 1 }: { v: number | null; digits?: number }) {
  const cls = v === null ? "muted" : v > 0.00005 ? "pos" : v < -0.00005 ? "neg" : "muted";
  return <span className={cls}>{fmtPct(v, digits)}</span>;
}

/** Etiqueta al final de la barra, siempre a la derecha (también en barras negativas). */
function BarValue(props: { x?: unknown; y?: unknown; width?: unknown; height?: unknown; value?: unknown }) {
  const x = Number(props.x ?? 0);
  const w = Number(props.width ?? 0);
  const y = Number(props.y ?? 0) + Number(props.height ?? 0) / 2;
  const v = Number(props.value ?? 0) / 100;
  return (
    <text x={Math.max(x, x + w) + 6} y={y} dy={4} fontSize={12} fill="var(--muted)">
      {fmtPct(v)}
    </text>
  );
}

function NameCell({ i, onOpen }: { i: Instrument; onOpen: (i: Instrument) => void }) {
  return (
    <td className="name">
      <button onClick={() => onOpen(i)} aria-label={`Ver gráfico de ${i.name}`}>
        {i.name}
      </button>
      <span className="sym" title={`Último dato: ${i.as_of}`}>
        {i.symbol}
        <span className="asof"> · {i.as_of}</span>
      </span>
    </td>
  );
}

function Trend({ i }: { i: Instrument }) {
  return (
    <td className="trend">
      <div className="trend-cell">
        <Sparkline values={i.spark} height={28} width={96} />
        <span
          className={`ma ${i.above_sma200 === null ? "" : i.above_sma200 ? "up" : "down"}`}
          title="Precio frente a su promedio de las últimas 200 sesiones"
        >
          {i.above_sma200 === null ? "—" : i.above_sma200 ? "▲ MM200" : "▼ MM200"}
        </span>
      </div>
    </td>
  );
}

export default function Market() {
  const { data, error, loading, reload } = useApi<MarketOverview>("/market/overview");
  const [period, setPeriod] = useState<Period>("change_ytd");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string>();
  const [open, setOpen] = useState<Instrument>();

  async function refresh() {
    setRefreshing(true);
    setRefreshError(undefined);
    try {
      await api.get("/market/overview?refresh=true");
      reload();
    } catch (e) {
      setRefreshError((e as Error).message);
    } finally {
      setRefreshing(false);
    }
  }

  const narrow = window.matchMedia("(max-width: 640px)").matches;
  const all = new Map((data?.groups.flatMap((g) => g.items) ?? []).map((i) => [i.symbol, i]));
  const headline = HEADLINE.map((s) => all.get(s)).filter((i): i is Instrument => Boolean(i));
  const sectors = data?.groups.find((g) => g.title.startsWith("Sectores"));
  const ranking = (sectors?.items ?? [])
    .filter((i) => i[period] !== null)
    .map((i) => ({ name: i.name, value: Number(((i[period] ?? 0) * 100).toFixed(2)) }))
    .sort((a, b) => b.value - a.value);
  const periodLabel = PERIODS.find((p) => p.key === period)?.label ?? "";

  // El hallazgo: cómo va el índice de referencia hoy y qué sector manda en el año.
  const spx = all.get("^GSPC");
  const ytd = [...(sectors?.items ?? [])].filter((i) => i.change_ytd !== null).sort((a, b) => (b.change_ytd ?? 0) - (a.change_ytd ?? 0));
  const finding =
    spx && ytd.length
      ? `El S&P 500 ${(spx.change_1d ?? 0) >= 0 ? "sube" : "baja"} ${fmtPct(Math.abs(spx.change_1d ?? 0), 2).replace("+", "")} hoy. En el año lidera ${ytd[0]!.name.toLowerCase()} (${fmtPct(ytd[0]!.change_ytd)}) y va último ${ytd[ytd.length - 1]!.name.toLowerCase()} (${fmtPct(ytd[ytd.length - 1]!.change_ytd)}).`
      : "Rendimiento por periodo y tendencia de los principales mercados.";

  return (
    <>
      <div className="page-head">
        <div>
          <div className="title-row">
            <h1>Mercados</h1>
            <Help topic="mercado" />
          </div>
          <div className="muted">{finding}</div>
        </div>
        <div className="row">
          {data && (
            <span className="muted small" title={data.source}>
              Actualizado {new Date(data.fetched_at).toLocaleTimeString("es-CR", { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
          <button onClick={refresh} disabled={refreshing}>
            {refreshing ? "Actualizando…" : "Actualizar"}
          </button>
        </div>
      </div>
      <Disclaimer />
      <ErrorNotice error={error ?? refreshError} />
      {loading && !data && <p className="muted">Descargando datos de mercado…</p>}

      {data && (
        <div className="grid grid-2">
          <div className="card table-wrap">
            <div className="card-head">
              <h2>Hoy</h2>
              <span className="muted small">Yahoo Finance · ≈15 min de retraso</span>
            </div>
            <table className="mkt compact">
              <thead>
                <tr>
                  <th>Instrumento</th>
                  <th className="num">Último</th>
                  <th className="num">Hoy</th>
                  <th className="num">Año</th>
                </tr>
              </thead>
              <tbody>
                {headline.map((i) => (
                  <tr key={i.symbol}>
                    <NameCell i={i} onOpen={setOpen} />
                    <td className="num">{fmtLast(i)}</td>
                    <td className="num">
                      <Pct v={i.change_1d} digits={2} />
                    </td>
                    <td className="num">
                      <Pct v={i.change_ytd} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {sectors && (
            <div className="card">
              <div className="card-head">
                <div className="title-row">
                  <h2>Rotación sectorial</h2>
                  <Help topic="mercado.sectores" />
                </div>
                <div className="row" role="group" aria-label="Periodo">
                  {PERIODS.map((p) => (
                    <button
                      key={p.key}
                      className={`chip ${period === p.key ? "on" : ""}`}
                      aria-pressed={period === p.key}
                      onClick={() => setPeriod(p.key)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
              <ResponsiveContainer width="100%" height={ranking.length * 39 + 12}>
                <BarChart data={ranking} layout="vertical" margin={{ left: 4, right: 64, top: 0, bottom: 0 }}>
                  <XAxis type="number" hide domain={[(min: number) => Math.min(0, min), "dataMax"]} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={narrow ? 104 : 150}
                    tick={{ fontSize: 13, fill: "var(--ink-2)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip formatter={(v) => [fmtPct(Number(v) / 100, 2), periodLabel]} cursor={{ fill: "var(--surface-2)" }} />
                  <Bar isAnimationActive={false} dataKey="value" radius={[2, 2, 2, 2]} barSize={14} label={BarValue}>
                    {ranking.map((r) => (
                      <Cell key={r.name} fill={r.value >= 0 ? "var(--pos)" : "var(--neg)"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {data && (
        <div className="card table-wrap">
          <div className="card-head">
            <h2>Panorama completo</h2>
            <span className="row small muted">
              ETFs amplios: <Help topic="mercado.etfs" label="¿Qué son?" />
            </span>
          </div>
          <div className="mkt-wrap">
            <table className="mkt">
              <thead>
                <tr>
                  <th>Instrumento</th>
                  <th className="num">Último</th>
                  <th className="num">Hoy</th>
                  <th className="num">1 sem</th>
                  <th className="num">1 mes</th>
                  <th className="num">Año</th>
                  <th className="num">12 m</th>
                  <th className="num" title="Distancia al máximo de las últimas 52 semanas">vs máx. 52 s</th>
                  <th className="num">Tendencia</th>
                </tr>
              </thead>
              {data.groups.map((g) => (
                <Fragment key={g.title}>
                  <tbody>
                    <tr className="group">
                      <th colSpan={9} scope="colgroup">
                        {g.title}
                      </th>
                    </tr>
                    {g.items.map((i) => (
                      <tr key={i.symbol}>
                        <NameCell i={i} onOpen={setOpen} />
                        <td className="num last">{fmtLast(i)}</td>
                        <td className="num">
                          <Pct v={i.change_1d} digits={2} />
                        </td>
                        <td className="num">
                          <Pct v={i.change_1w} />
                        </td>
                        <td className="num">
                          <Pct v={i.change_1m} />
                        </td>
                        <td className="num">
                          <Pct v={i.change_ytd} />
                        </td>
                        <td className="num">
                          <Pct v={i.change_1y} />
                        </td>
                        <td className="num muted">{i.from_52w_high === null ? "—" : i.from_52w_high > -0.005 ? "En máximos" : fmtPct(i.from_52w_high)}</td>
                        <Trend i={i} />
                      </tr>
                    ))}
                  </tbody>
                </Fragment>
              ))}
            </table>
          </div>
          {data.missing.length > 0 && <p className="muted small">Sin datos: {data.missing.join(", ")}</p>}
        </div>
      )}
      {open && <ChartDrawer inst={open} onClose={() => setOpen(undefined)} />}
    </>
  );
}
