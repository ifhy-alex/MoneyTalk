import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useApi } from "../hooks";
import type { Instrument } from "../types-market";
import { Icons } from "./icons";
import { Change, Figure } from "./ui";

interface History {
  symbol: string;
  range: string;
  points: { date: string; close: number }[];
  change: number | null;
}

const RANGES = ["1M", "3M", "6M", "1A", "5A"];

/** Panel lateral con el historial de un instrumento en distintos rangos. */
export default function ChartDrawer({ inst, onClose }: { inst: Instrument; onClose: () => void }) {
  const [range, setRange] = useState("1A");
  const { data, error, loading } = useApi<History>(`/market/history/${encodeURIComponent(inst.symbol)}?range=${range}`);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const up = (data?.change ?? 0) >= 0;
  const color = up ? "#1c8d68" : "#c4503a";
  const rows: [string, number | null][] = [
    ["1 semana", inst.change_1w],
    ["1 mes", inst.change_1m],
    ["3 meses", inst.change_3m],
    ["En el año", inst.change_ytd],
    ["12 meses", inst.change_1y],
    ["vs máximo 52 sem.", inst.from_52w_high],
  ];

  return createPortal(
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer wide" role="dialog" aria-modal="true" aria-label={inst.name} onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <div>
            <h2>{inst.name}</h2>
            <div className="muted small">{inst.symbol}</div>
          </div>
          <button className="nav" aria-label="Cerrar" onClick={onClose}>
            {Icons.close}
          </button>
        </div>
        <div className="row" style={{ alignItems: "baseline", gap: 14 }}>
          <span className="inst-last">
            <Figure text={inst.last.toLocaleString("es-CR", { maximumFractionDigits: 2 })} />
          </span>
          <Change value={inst.change_1d} />
          <span className="muted small">hoy · {inst.as_of}</span>
        </div>
        <div className="row" style={{ margin: "16px 0 8px" }}>
          {RANGES.map((r) => (
            <button key={r} className={`chip ${range === r ? "on" : ""}`} onClick={() => setRange(r)}>
              {r}
            </button>
          ))}
          <span className="spacer" />
          {data && <Change value={data.change} />}
        </div>
        {error && <div className="notice error">{error}</div>}
        <div style={{ height: 300, opacity: loading ? 0.5 : 1 }}>
          {data && data.points.length > 1 && (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.points}>
                <defs>
                  <linearGradient id="hist" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={0.28} />
                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={50} tickFormatter={(d: string) => d.slice(2, 7)} />
                <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} width={60} tickFormatter={(v: number) => v.toLocaleString("es-CR", { maximumFractionDigits: 0 })} />
                <Tooltip
                  formatter={(v) => Number(v).toLocaleString("es-CR", { maximumFractionDigits: 2 })}
                  contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 10, fontSize: 13 }}
                />
                <Area isAnimationActive={false} dataKey="close" name="Cierre" stroke={color} strokeWidth={2} fill="url(#hist)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
        <h3>Rendimiento por periodo</h3>
        <dl>
          {rows.map(([label, v]) => (
            <div key={label} className="row">
              <dt style={{ flex: 1, fontWeight: 500 }}>{label}</dt>
              <dd>
                <Change value={v} />
              </dd>
            </div>
          ))}
        </dl>
        <div className="drawer-tip">
          Promedio móvil de 200 sesiones: el precio está {inst.above_sma200 === null ? "—" : inst.above_sma200 ? "por encima (tendencia alcista de largo plazo)" : "por debajo (tendencia bajista de largo plazo)"}.
          Volatilidad del último mes (anualizada): {inst.volatility_1m === null ? "—" : `${(inst.volatility_1m * 100).toFixed(1)} %`}.
        </div>
      </aside>
    </div>,
    document.body,
  );
}
