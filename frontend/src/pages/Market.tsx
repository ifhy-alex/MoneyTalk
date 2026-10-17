import { useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api";
import { Change, Disclaimer, ErrorNotice, Figure, SectionTitle, Sparkline } from "../components/ui";
import { useApi } from "../hooks";
import type { Instrument, MarketOverview } from "../types-market";
import ChartDrawer from "../components/ChartDrawer";
import Help from "../components/Help";

type Period = "change_1d" | "change_1w" | "change_1m" | "change_3m" | "change_ytd" | "change_1y";
const PERIODS: { key: Period; label: string }[] = [
  { key: "change_1d", label: "1D" },
  { key: "change_1w", label: "1S" },
  { key: "change_1m", label: "1M" },
  { key: "change_3m", label: "3M" },
  { key: "change_ytd", label: "Año" },
  { key: "change_1y", label: "12M" },
];

const fmtLast = (i: Instrument) =>
  i.symbol === "CRC=X"
    ? `₡${i.last.toFixed(2)}`
    : i.symbol === "^TNX"
      ? `${i.last.toFixed(2)} %`
      : i.last.toLocaleString("es-CR", { maximumFractionDigits: i.last < 10 ? 4 : 2 });

/** Etiqueta al final de la barra, siempre a la derecha (también en barras negativas). */
function BarValue(props: { x?: unknown; y?: unknown; width?: unknown; height?: unknown; value?: unknown }) {
  const x = Number(props.x ?? 0);
  const w = Number(props.width ?? 0);
  const y = Number(props.y ?? 0) + Number(props.height ?? 0) / 2;
  const v = Number(props.value ?? 0);
  return (
    <text x={Math.max(x, x + w) + 6} y={y} dy={4} fontSize={11} fill="var(--muted)" fontFamily="var(--font-mono)">
      {`${v >= 0 ? "+" : ""}${v.toFixed(1)}%`}
    </text>
  );
}

function InstrumentCard({ i, onOpen }: { i: Instrument; onOpen: (i: Instrument) => void }) {
  return (
    <div className="card inst">
      <div className="inst-top">
        <div>
          <div className="inst-name">{i.name}</div>
          <div className="inst-sym">
            {i.symbol} · {i.as_of}
          </div>
        </div>
        <Change value={i.change_1d} />
      </div>
      <div className="inst-last">
        <Figure text={fmtLast(i)} />
      </div>
      <Sparkline values={i.spark} height={40} />
      <div className="periods">
        {PERIODS.slice(1).map((p) => {
          const v = i[p.key];
          return (
            <div key={p.key}>
              <div className="p-l">{p.label}</div>
              <div className={`p-v ${v === null ? "muted" : v >= 0 ? "pos" : "neg"}`}>
                {v === null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}`}
              </div>
            </div>
          );
        })}
      </div>
      <div className="inst-foot">
        <button className="link small" onClick={() => onOpen(i)}>
          Ver gráfico
        </button>
        {i.above_sma200 !== null && (
          <span className={`badge ${i.above_sma200 ? "ok" : "bad"}`} title="Precio contra su promedio de 200 sesiones">
            {i.above_sma200 ? "▲" : "▼"} MM200
          </span>
        )}
        {i.above_sma50 !== null && (
          <span className={`badge ${i.above_sma50 ? "ok" : "bad"}`} title="Precio contra su promedio de 50 sesiones">
            {i.above_sma50 ? "▲" : "▼"} MM50
          </span>
        )}
        {i.from_52w_high !== null && (
          <span className="badge" title="Distancia al máximo de 52 semanas">
            {i.from_52w_high > -0.005 ? "En máximos" : `${(i.from_52w_high * 100).toFixed(1)} % vs máx.`}
          </span>
        )}
      </div>
    </div>
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
  const sectors = data?.groups.find((g) => g.title.startsWith("Sectores"));
  const ranking = (sectors?.items ?? [])
    .filter((i) => i[period] !== null)
    .map((i) => ({ name: i.name, value: Number(((i[period] ?? 0) * 100).toFixed(2)) }))
    .sort((a, b) => b.value - a.value);
  const others = data?.groups.filter((g) => g !== sectors) ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Mercados</div>
          <div className="title-row">
            <h1>Panorama y tendencias</h1>
            <Help topic="mercado" />
          </div>
          <div className="muted">
            Rendimiento por periodo, precio frente a sus promedios móviles y distancia al máximo anual. Son hechos
            medibles, no pronósticos.
          </div>
        </div>
        <div className="row">
          {data && (
            <span className="muted small">
              {data.source} · {new Date(data.fetched_at).toLocaleString("es-CR")}
            </span>
          )}
          <button onClick={refresh} disabled={refreshing}>
            {refreshing ? "Actualizando…" : "Actualizar ahora"}
          </button>
        </div>
      </div>
      <Disclaimer />
      <ErrorNotice error={error ?? refreshError} />
      {loading && !data && <p className="muted">Descargando datos de mercado (unos segundos la primera vez)…</p>}

      {sectors && (
        <div className="card">
          <div className="card-head">
            <div className="title-row">
              <h2>Rotación sectorial</h2>
              <Help topic="mercado.sectores" />
            </div>
            <div className="row">
              {PERIODS.map((p) => (
                <button key={p.key} className={`chip ${period === p.key ? "on" : ""}`} onClick={() => setPeriod(p.key)}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={ranking.length * 28 + 20}>
            <BarChart data={ranking} layout="vertical" margin={{ left: 10, right: 52 }}>
              <XAxis type="number" hide domain={["dataMin", "dataMax"]} />
              <YAxis type="category" dataKey="name" width={narrow ? 104 : 170} tick={{ fontSize: narrow ? 11 : 12, fill: "var(--ink-2)" }} axisLine={false} tickLine={false} />
              <Tooltip formatter={(v) => `${Number(v).toFixed(2)} %`} cursor={{ fill: "var(--surface-2)" }} />
              <Bar dataKey="value" radius={[3, 3, 3, 3]} barSize={16} label={BarValue}>
                {ranking.map((r) => (
                  <Cell key={r.name} fill={r.value >= 0 ? "#1c8d68" : "#c4503a"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {others.map((g) => (
        <section key={g.title}>
          <SectionTitle aside={g.title.startsWith("ETF") ? <Help topic="mercado.etfs" label="¿Qué son?" /> : undefined}>{g.title}</SectionTitle>
          <div className="instruments">
            {g.items.map((i) => (
              <InstrumentCard key={i.symbol} i={i} onOpen={setOpen} />
            ))}
          </div>
        </section>
      ))}
      {sectors && (
        <section>
          <SectionTitle aside={<Help topic="mercado.sectores" />}>{sectors.title}</SectionTitle>
          <div className="instruments">
            {sectors.items.map((i) => (
              <InstrumentCard key={i.symbol} i={i} onOpen={setOpen} />
            ))}
          </div>
        </section>
      )}
      {open && <ChartDrawer inst={open} onClose={() => setOpen(undefined)} />}
      {data?.missing.length ? <p className="muted small">Sin datos: {data.missing.join(", ")}</p> : null}
    </>
  );
}
