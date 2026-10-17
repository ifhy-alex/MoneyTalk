import type { ReactNode } from "react";

export const CHART = {
  accent: "#1c8d68",
  accent2: "#4f74c8",
  warn: "#c48a22",
  danger: "#c4503a",
  grid: "#8a8a7a33",
  palette: ["#1c8d68", "#4f74c8", "#c48a22", "#8e5fb5", "#c4503a", "#2a9db5", "#7f8c3a", "#b5651d", "#6c757d"],
};

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="muted small hint">{hint}</div>}
    </div>
  );
}

export function Progress({ ratio }: { ratio: number }) {
  const cls = ratio >= 1 ? "bad" : ratio >= 0.8 ? "warn" : "";
  return (
    <div className={`progress ${cls}`} title={`${(ratio * 100).toFixed(0)} %`}>
      <div style={{ width: `${Math.min(ratio, 1) * 100}%` }} />
    </div>
  );
}

export function ErrorNotice({ error }: { error?: string }) {
  return error ? <div className="notice error">{error}</div> : null;
}

export function Disclaimer() {
  return (
    <div className="disclaimer">
      <span aria-hidden>⚖</span>
      <span>
        <b>No es asesoría financiera.</b> Las señales se calculan con criterios que vos definís y se muestran con su
        evidencia. Los datos de mercado pueden tener retrasos o errores; verificá con fuentes oficiales antes de decidir.
      </span>
    </div>
  );
}

export function Change({ value, digits = 2 }: { value: number | null | undefined; digits?: number }) {
  if (value === null || value === undefined) return <span className="pill flat">—</span>;
  const cls = value > 0.00005 ? "up" : value < -0.00005 ? "down" : "flat";
  const sign = value > 0 ? "+" : "";
  return <span className={`pill ${cls}`}>{`${sign}${(value * 100).toFixed(digits)} %`}</span>;
}

/** Mini gráfico de línea en SVG puro (sin ejes) para tarjetas y cintas. */
export function Sparkline({ values, width = 120, height = 34 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * width, height - 2 - ((v - min) / span) * (height - 4)]);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x!.toFixed(1)},${y!.toFixed(1)}`).join(" ");
  const up = values[values.length - 1]! >= values[0]!;
  const color = up ? "var(--pos)" : "var(--neg)";
  const id = `sg${Math.round(values[0]! * 1000) % 100000}${values.length}${up ? "u" : "d"}`;
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${d} L${width},${height} L0,${height} Z`} fill={`url(#${id})`} />
      <path d={d} fill="none" stroke={color} strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="section-title">
      <h2>{children}</h2>
      <span className="line" />
      {aside}
    </div>
  );
}
